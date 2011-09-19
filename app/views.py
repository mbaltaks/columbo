from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, loader
from django.http import HttpResponse
from django.utils import simplejson
from app.models import *
import calendar
import datetime
import urllib
import urllib2
import re
import sys
import base64
import secret_settings
from djangoappengine.utils import on_production_server, have_appserver


use_oauth = True
if on_production_server:
    use_oauth = True
else:
    use_oauth = False
    try:
        import secret_settings
    except ImportError, e:
        pass


# http://developer.github.com/v3/
github_api_base_address = 'https://api.github.com/repos/'
github_authorise_address = 'https://github.com/login/oauth/authorize'
github_access_token_address = 'https://github.com/login/oauth/access_token'
github_api_result_cache_lifetime = 60 * 60 * 23

work_day_hours = 7

ideal_remaining = 'hours_remaining_ideal'
actual_remaining = 'hours_remaining_actual'
ideal_spent = 'ideal_hours_spent_so_far'
actual_spent = 'actual_hours_spent_so_far'

# What list of issues can I get? New since a date? I want a local copy
# of each issue, with the hour estimated extracted, and the total of hours
# spent so far, which might still continue once the issue is closed.
# Ability to sort by user assigned, project label (from the title?),
# milestone.


# ----------------------------------------------------------------------------
def datetime_json_handler(obj):
    if hasattr(obj, 'strftime'):
        return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        return str(obj)


def date_plus_weekdays(date, weekdays):
    new_date = date + datetime.timedelta(weekdays)
    return new_date
    day = date.date.day
    month = date.date.month
    year = date.date.year
    days_to_add = weekdays
    start_date = datetime.date(date.date.year, date.date.month, date.date.day)
    new_date = start_date
    while (days_to_add > 0):
        new_date += datetime.timedelta(1)
        if new_date.isoweekday() not in (6, 7):
            pass
        day_of_week = calendar.calendar.weekday(year, month, day)


def add_values_to_dict(dict, key, data_values):
    if key not in dict:
        dict[key] = {}
        for v in data_values:
            dict[key][v] = 0.0
    for v, value in data_values.items():
        dict[key][v] += value
    return dict


# ----------------------------------------------------------------------------
def data_from_address(address):
    try:
        gr = GithubAPIResult.objects.filter(address=address)[0]
        cache_stale = ((gr.date_modified + datetime.timedelta(seconds=gr.lifetime)) < datetime.datetime.utcnow())
    except IndexError, e:
        cache_stale = True
    if cache_stale:
        if use_oauth:
            stored_token = OAuthToken.objects.all()[0]
            req_address =  address + '&%s' % stored_token.token
            req = urllib2.Request(req_address)
        else:
            stored_credentials = BasicCredential.objects.all()[0]
            req = urllib2.Request(address)
            base64string = base64.encodestring(
                        '%s:%s' % (stored_credentials.username, stored_credentials.password))[:-1]
            authheader =  "Basic %s" % base64string
            req.add_header("Authorization", authheader)
        # TODO: catch a 401 and delete the credentials (both)
        url_result = urllib2.urlopen(req)
        json = url_result.read()
        try:
            gr = GithubAPIResult.objects.filter(address=address)[0]
            gr.lifetime = github_api_result_cache_lifetime
            gr.data = json
            gr.date_modified = datetime.datetime.utcnow()
        except IndexError, e:
            gr = GithubAPIResult(lifetime=github_api_result_cache_lifetime, address=address, data=json, date_modified=datetime.datetime.utcnow())
        gr.save()
    else:
        json = gr.data
    return json


def all_items_for_github_api(base_address):
    page = 1
    keep_going = True
    all_items = []
    while keep_going:
        address = base_address + '&page=' + str(page)
        json = data_from_address(address)
        page += 1
        data = simplejson.loads(json)
        if len(data) < 1:
            keep_going = False
        else:
            for item in data:
                all_items.append(item)
    return all_items


# ----------------------------------------------------------------------------
def milestone_for_issue(issue):
    pass


def owner_for_issue(issue):
    owner = 'NoOwnerAssigned'
    if issue != None and issue['assignee'] != None and len(issue['assignee']['login']) > 0:
        owner = issue['assignee']['login']
    return owner


def project_for_issue(issue):
    project = 'NoProjectSet'
    r = re.compile('.*\[(.+)\].*')
    m = r.match(issue['title'])
    if m:
        project = str(m.group(1))
    return project


def hours_spent_for_comment(comment):
    hours = 0.0
    r = re.compile('.*\(([0-9\.]+)h\).*')
    m = r.match(comment['body'])
    if m:
        hours = float(m.group(1))
    return hours


def hours_required_for_issue(issue):
    hours = 0.0
    r = re.compile('.*\(([0-9\.]+)h\).*')
    m = r.match(issue['title'])
    if m:
        hours = float(m.group(1))
    return hours


def comments_for_issue(issue):
    comments = []
    if issue['comments'] != 0:
        page = 1
        while len(comments) < issue['comments']:
            comment_list_address = github_api_base_address + secret_settings.github_repo + '/issues/' + str(issue['number']) + '/comments?per_page=100&page=' + str(page)
            json = data_from_address(comment_list_address)
            page += 1
            comments_data = simplejson.loads(json)
            for comment in comments_data:
                comments.append(comment)
    return comments


def completed_hours_for_issue(issue):
    hours = 0.0
    all_comments = comments_for_issue(issue)
    for comment in all_comments:
        hours += hours_spent_for_comment(comment)
    return hours


def hours_for_owner_project(issue):
    assigned_to = u'Nobody'
    project = u'None'
    hours = 0.0
    labels = issue['labels']
    for label in labels:
        if label[0] == '@':
            assigned_to = label
        elif label[0] == '|':
            project = label
    hours = hours_for_issue(issue)
    if hours == 0:
        # A task that is hard to estimate will take a while.
        hours = 0.0 # But we can't know everything.
    return assigned_to, project, hours


def issues_for_milestone(milestone):
    base_address = github_api_base_address + secret_settings.github_repo + '/issues?per_page=100'
    base_address += '&milestone=' + str(milestone['number'])
    issues = all_items_for_github_api(base_address)
    base_address += '&state=closed'
    closed_issues = all_items_for_github_api(base_address)
    for issue in closed_issues:
        issues.append(issue)
    return issues


def fetch_all_milestones():
    base_address = github_api_base_address + secret_settings.github_repo + '/milestones?per_page=100'
    open_milestones = all_items_for_github_api(base_address)
    base_address += '&state=closed'
    closed_milestones = all_items_for_github_api(base_address)
    for item in closed_milestones:
        open_milestones.append(item)
    return open_milestones


# ----------------------------------------------------------------------------
def github_login(request):
    scope = 'repo'
    address = github_authorise_address
    address += '?'
    address += 'client_id=' + secret_settings.github_client_id
    #address += '&'
    #address += 'redirect_uri=' + secret_settings.github_login_redirect_address
    address += '&'
    address += 'scope=' + scope
    return redirect(address)


def github_callback(request):
    code = request.GET['code']
    address = github_access_token_address
    params = {
        'client_id': secret_settings.github_client_id,
        #'redirect_uri': secret_settings.github_request_token_redirect_address,
        'client_secret': secret_settings.github_secret,
        'code': code,
        }
    post_data = urllib.urlencode(params)
    req = urllib2.Request(address, post_data)
    url_result = urllib2.urlopen(req)
    token = url_result.read()
    try:
        stored_token = OAuthToken.objects.all()[0]
        stored_token.token = token
    except IndexError, e:
        stored_token = OAuthToken(token=token)
    stored_token.save()
    return index(request)


# ----------------------------------------------------------------------------
def index(request):
    links = {'/burndown': 'Burndown charts', '/schedule': 'Schedule'}
    if use_oauth:
        try:
            stored_token = OAuthToken.objects.all()[0]
        except IndexError, e:
            links['/login'] = 'Login to Github'
    return render_to_response('index.html', {'links': links}, context_instance = RequestContext(request))


# ----------------------------------------------------------------------------
def schedule(request):
    # TODO: archive the label support, and switch to using the assigned owner, and milestone.
    # I want to get a view of number of working days left, which we can then compare with
    # the date set in the milestone. If I can find a way to automate that, even better.
    # TODO: check for an access token, if none or it doesn't work, login to github again.
    base_address = github_api_base_address + secret_settings.github_repo + '/issues?per_page=100'
    all_open_issues = all_items_for_github_api(base_address)
    no_owner = []
    issues_per_owner = {}
    person_times = {}
    project_times = {}
    person_project_times = {}
    for issue in all_open_issues:
        person = owner_for_issue(issue)
        project = project_for_issue(issue)
        person_project = u'' + person + u' - ' + project

        hours_required = hours_required_for_issue(issue)
        hours_spent = completed_hours_for_issue(issue)
        hours_remaining = hours_required - hours_spent

        working_days_required = round(hours_required / work_day_hours, 1)
        working_days_spent = round(hours_spent / work_day_hours, 1)
        working_days_remaining = round(hours_remaining / work_day_hours, 1)
        now = datetime.datetime.utcnow()
        times = {
            'hours_required': hours_required,
            'hours_spent': hours_spent,
            'hours_remaining': hours_remaining,
            'days_required': working_days_required,
            'days_spent': working_days_spent,
            'days_remaining': working_days_remaining,
            }

        person_times = add_values_to_dict(person_times, person, times)
        project_times = add_values_to_dict(project_times, project, times)
        person_project_times = add_values_to_dict(person_project_times, person_project, times)

        if person == 'NoOwnerAssigned':
            no_owner.append(issue['html_url'])
        issues_per_owner[person] = issue

    data = ""
    if request.method == 'GET':
        if (request.GET.__contains__('json')):
            data = request.GET.__getitem__('json')
    elif request.method == 'POST':
        data = request.raw_post_data.decode("utf-8")
    method = request.method
    links = {'/burndown': 'Burndown charts', '/schedule': 'Schedule'}
    if use_oauth:
        try:
            stored_token = OAuthToken.objects.all()[0]
        except IndexError, e:
            links['/login'] = 'Login to Github'
    return render_to_response('schedule.html', {'no_owner': no_owner, 'person_times' : person_times, 'project_times': project_times, 'person_project_times': person_project_times, 'links': links}, context_instance = RequestContext(request))


# ----------------------------------------------------------------------------
def burndown_hours(issues):
    hours_required_dict = {}
    hours_spent_dict = {}
    for issue in issues:
        #timestamp = datetime.datetime.strptime(issue['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        timestamp = issue['created_at']
        hours_required = hours_required_for_issue(issue)
        if timestamp not in hours_required_dict:
            hours_required_dict[timestamp] = 0.0
        hours_required_dict[timestamp] += hours_required

        comments = comments_for_issue(issue)
        for comment in comments:
            hours_spent = hours_spent_for_comment(comment)
            #timestamp = datetime.datetime.strptime(comment['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            timestamp = comment['created_at']
            if timestamp not in hours_spent_dict:
                hours_spent_dict[timestamp] = 0.0
            hours_spent_dict[timestamp] += hours_spent
    return hours_required_dict, hours_spent_dict


# ----------------------------------------------------------------------------
def burndown_buckets(hours_required, hours_spent):
    total_hours_required = 0.0
    for time, hours in hours_required.items():
        timestamp = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')
        date = timestamp.strftime('%Y-%m-%d')
        total_hours_required += hours

    total_hours_spent = 0.0
    hours_spent_out = {}
    for time, hours in hours_spent.items():
        timestamp = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')
        date = timestamp.strftime('%Y-%m-%d')
        total_hours_spent += hours
        if date not in hours_spent_out:
            hours_spent_out[date] = 0.0
        hours_spent_out[date] += hours
    return total_hours_required, total_hours_spent, hours_spent_out


# ----------------------------------------------------------------------------
def burndown_stuff(hours_required, hours_spent, hours_spent_dict, man_hours_per_date):
    data = {}
    ideal_hours_spent_so_far = 0.0
    actual_hours_spent_so_far = 0.0
    dates = sorted(hours_spent_dict.keys())
    for date in dates:
        ideal_hours_spent_so_far += man_hours_per_date
        actual_hours_spent_so_far += hours_spent_dict[date]
        if date not in data:
            data[date] = {}
        data[date][ideal_spent] = ideal_hours_spent_so_far
        data[date][actual_spent] = actual_hours_spent_so_far
        data[date][ideal_remaining] = hours_required - ideal_hours_spent_so_far
        data[date][actual_remaining] = hours_required - actual_hours_spent_so_far
    return data


# ----------------------------------------------------------------------------
def burndown_data(milestone, issues, man_hours_per_date):
    hours_required_dict, hours_spent_dict = burndown_hours(issues)
    hours_required, hours_spent, hours_spent_per_date = burndown_buckets(hours_required_dict, hours_spent_dict)
    data = burndown_stuff(hours_required, hours_spent, hours_spent_per_date, man_hours_per_date)
    return data


# ----------------------------------------------------------------------------
def burndown_data_old(milestone, issues, man_hours_per_date):
    data = {}
    hours_required = 0.0
    for issue in issues:
        hours_required += hours_required_for_issue(issue)
    if milestone['due_on'] != None:
        end_timestamp = datetime.datetime.strptime(milestone['due_on'], '%Y-%m-%dT%H:%M:%SZ')
    # TODO: switch to local day buckets:
    # http://www.enricozini.org/2009/debian/using-python-datetime/
    # http://stackoverflow.com/questions/1398674/python-display-the-time-in-a-different-time-zone
        end_date_string = end_timestamp.strftime('%Y-%m-%d')
        data[end_date_string] = {}
        data[end_date_string][ideal_remaining] = hours_required
        data[end_date_string][actual_remaining] = hours_required
        data[end_date_string][actual_spent] = 0.0
        data[end_date_string][ideal_spent] = 0.0
    for issue in issues:
        #issue_hours = hours_required_for_issue(issue)
        comments = comments_for_issue(issue)
        for comment in comments:
            hours_spent = hours_spent_for_comment(comment)
            timestamp = datetime.datetime.strptime(comment['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            date_string = timestamp.strftime('%Y-%m-%d')
            if date_string not in data:
                data[date_string] = {}
                data[date_string][actual_remaining] = hours_required
                data[date_string][ideal_remaining] = hours_required
                data[date_string][actual_spent] = 0.0
                data[date_string][ideal_spent] = 0.0
            data[date_string][actual_spent] += hours_spent
    dates = sorted(data.keys())
    previous_date = ''
    actual_hours_spent_so_far = 0.0
    ideal_hours_spent_so_far = 0.0
    for date in dates:
        ideal_hours_spent_so_far += man_hours_per_date
        actual_hours_spent_so_far += data[date][actual_spent]
        data[date_string][ideal_spent] = ideal_hours_spent_so_far
        data[date][ideal_remaining] -= ideal_hours_spent_so_far
        data[date][actual_remaining] -= actual_hours_spent_so_far
    return data


# ----------------------------------------------------------------------------
def burndown(request):
    chosen_milestone = {}
    milestone_number = 0
    milestone_title = 'No Milestones'
    data = {}
    team_size = 1
    if request.method == 'POST':
        milestone_number = int(request.POST['milestone'])
        team_size = float(request.POST['team_size'])
    team_daily_work_hours = team_size * work_day_hours
    all_milestones = fetch_all_milestones()
    options = {}
    due_date = ''
    for m in all_milestones:
        options[m['number']] = m['title']
        if m['number'] == milestone_number:
            chosen_milestone = m
            if chosen_milestone['due_on'] != None:
                end_timestamp = datetime.datetime.strptime(chosen_milestone['due_on'], '%Y-%m-%dT%H:%M:%SZ')
                due_date = end_timestamp.strftime('%Y-%m-%d')
    if milestone_number > 0 and milestone_number in options:
        milestone_title = options[milestone_number]
        issues = issues_for_milestone(chosen_milestone)
        data = burndown_data(chosen_milestone, issues, team_daily_work_hours)
    posted = {'milestone_number': milestone_number, 'milestone_title': milestone_title, 'team_size': team_size}
    graph_date = sorted(data.keys())
    x_length = len(graph_date)
    max_hours = 0.0
    graph_actual = []
    graph_ideal = []
    for d in graph_date:
        graph_actual.append(data[d]['hours_remaining_actual'])
        graph_ideal.append(data[d]['hours_remaining_ideal'])
        if data[d]['hours_remaining_actual'] > max_hours:
            max_hours = data[d]['hours_remaining_actual']
        if data[d]['hours_remaining_ideal'] > max_hours:
            max_hours = data[d]['hours_remaining_ideal']
    links = {'/burndown': 'Burndown charts', '/schedule': 'Schedule'}
    if use_oauth:
        try:
            stored_token = OAuthToken.objects.all()[0]
        except IndexError, e:
            links['/login'] = 'Login to Github'
    return render_to_response('burndown.html', {'data': data, 'options': options, 'action': '/burndown', 'posted': posted, 'graph_date': graph_date, 'graph_actual': graph_actual, 'graph_ideal': graph_ideal, 'x_length': x_length, 'y_height': max_hours, 'links': links, 'due_date': due_date}, context_instance = RequestContext(request))
