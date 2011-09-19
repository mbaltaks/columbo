"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from app.models import *
from app.views import *


class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.assertEqual(1 + 1, 2)


    def test_hours_and_timestamps(self):
        hours_required = {
            '2011-09-01T00:00:00Z': 4,
            '2011-09-01T00:00:01Z': 4,
            '2011-09-01T00:00:02Z': 4,
            '2011-09-01T00:00:03Z': 4,
            }
        hours_spent = {
            '2011-09-02T00:00:00Z': 1,
            '2011-09-03T00:00:00Z': 2,
            '2011-09-04T00:00:00Z': 2,
            '2011-09-05T00:00:00Z': 1,
            '2011-09-06T00:00:00Z': 4,
            '2011-09-07T00:00:00Z': 4,
            #'2011-09-08T00:00:00Z': 4,
            }
        total_hours_required, total_hours_spent, hours_spent = burndown_buckets(hours_required, hours_spent)
        self.assertEqual(total_hours_required, 16)
        self.assertEqual(total_hours_spent, 14)
        out = {'2011-09-03': 2.0, '2011-09-02': 1.0, '2011-09-07': 4.0, '2011-09-06': 4.0, '2011-09-05': 1.0, '2011-09-04': 2.0}
        self.assertEqual(hours_spent, out)
