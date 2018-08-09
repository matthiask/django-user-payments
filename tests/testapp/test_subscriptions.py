from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from user_payments.models import LineItem, Payment
from user_payments.user_subscriptions.models import Subscription, SubscriptionPeriod


def zero_management_form_data(prefix):
    return {
        "%s-TOTAL_FORMS" % prefix: 0,
        "%s-INITIAL_FORMS" % prefix: 0,
        "%s-MIN_NUM_FORMS" % prefix: 0,
        "%s-MAX_NUM_FORMS" % prefix: 1000,
    }


def merge_dicts(*dicts):
    res = {}
    for d in dicts:
        res.update(d)
    return res


class Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def pay_period(self, period, user=None):
        period.create_line_item()
        payment = Payment.objects.create_pending(user=user or self.user)
        payment.charged_at = timezone.now()
        payment.save()

    def test_model(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2040, 1, 1),
        )
        self.assertEqual(subscription.starts_at.date(), date(2040, 1, 1))
        self.assertEqual(subscription.ends_at, None)

        self.assertEqual(SubscriptionPeriod.objects.count(), 0)
        Subscription.objects.create_periods()
        self.assertEqual(SubscriptionPeriod.objects.count(), 0)

        subscription.create_periods(until=date(2040, 3, 31))

        self.assertEqual(SubscriptionPeriod.objects.count(), 3)
        self.assertEqual(LineItem.objects.count(), 0)

        SubscriptionPeriod.objects.create_line_items()
        self.assertEqual(LineItem.objects.count(), 0)

        SubscriptionPeriod.objects.create_line_items(until=date(2040, 3, 31))
        self.assertEqual(LineItem.objects.count(), 3)

        payment = Payment.objects.create_pending(user=self.user)
        self.assertEqual(payment.amount, 180)

        subscription.create_periods(until=date(2040, 4, 1))
        self.assertEqual(SubscriptionPeriod.objects.count(), 4)

        subscription.refresh_from_db()
        # Not paid yet.
        self.assertEqual(subscription.paid_until, date(2039, 12, 31))

        payment.charged_at = timezone.now()
        payment.save()

        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, date(2040, 3, 31))

        self.assertEqual(self.user.user_subscriptions.for_code("test1"), subscription)
        self.assertEqual(self.user.user_subscriptions.for_code("something"), None)

    def test_starts_on(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test2",
            title="Test subscription 2",
            periodicity="yearly",
            amount=0,
        )
        self.assertEqual(subscription.starts_on, date.today())

        self.assertTrue(subscription.is_active)
        self.assertTrue(subscription.in_grace_period)

        self.pay_period(subscription.create_periods()[-1])

        subscription.refresh_from_db()

        self.assertTrue(subscription.is_active)
        self.assertFalse(subscription.in_grace_period)

    def test_ends_on(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test3",
            title="Test subscription 3",
            periodicity="weekly",
            amount=0,
            starts_on=date(2016, 1, 1),
            ends_on=date(2016, 1, 31),
        )

        periods = subscription.create_periods()
        self.assertEqual(
            [p.ends_on for p in periods],
            [
                date(2016, 1, 7),
                date(2016, 1, 14),
                date(2016, 1, 21),
                date(2016, 1, 28),
                date(2016, 2, 4),
            ],
        )

        self.assertTrue(
            tuple(subscription.ends_at.timetuple())[:6], (2016, 1, 31, 23, 59, 59)
        )

        self.assertEqual(
            tuple(periods[0].starts_at.timetuple())[:6], (2016, 1, 1, 0, 0, 0)
        )
        self.assertEqual(
            tuple(periods[0].ends_at.timetuple())[:6], (2016, 1, 7, 23, 59, 59)
        )

    def test_autorenewal(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test4",
            title="Test subscription 4",
            periodicity="weekly",
            amount=0,
            starts_on=date.today() - timedelta(days=30),
        )

        # Exactly one period
        period, = subscription.create_periods(until=subscription.starts_on)
        self.assertEqual(LineItem.objects.count(), 0)
        period.create_line_item()
        self.assertEqual(LineItem.objects.count(), 1)
        period.create_line_item()
        self.assertEqual(LineItem.objects.count(), 1)
        payment = Payment.objects.create_pending(user=self.user)
        payment.charged_at = timezone.now()
        payment.save()

        self.assertEqual(
            Subscription.objects.filter(renew_automatically=True).count(), 1
        )
        Subscription.objects.disable_autorenewal()
        self.assertEqual(
            Subscription.objects.filter(renew_automatically=True).count(), 0
        )

        # Restart the subscription
        Subscription.objects.ensure(
            user=self.user, code="test4", starts_on=date.today(), ends_on=None
        )
        subscription.refresh_from_db()

        periods = subscription.create_periods()
        self.assertEqual([p.starts_on for p in periods], [date.today()])
        self.assertEqual(
            [p.starts_on for p in subscription.periods.all()],
            [date.today() - timedelta(days=30), date.today()],
        )

    def test_manager_create_periods(self):
        Subscription.objects.ensure(
            user=self.user,
            code="sub1",
            periodicity="weekly",
            amount=10,
            renew_automatically=True,  # The default, therefore redundant
        )
        Subscription.objects.ensure(
            user=self.user,
            code="sub2",
            periodicity="weekly",
            amount=10,
            renew_automatically=False,
        )

        Subscription.objects.create_periods()

        self.assertEqual(
            list(
                SubscriptionPeriod.objects.values_list("subscription__code", flat=True)
            ),
            ["sub1"],
        )

    def test_admin_create(self):
        client = self.login()
        response = client.post(
            "/admin/user_subscriptions/subscription/add/",
            merge_dicts(
                {
                    "user": self.user.pk,
                    "code": "yay",
                    "title": "yay",
                    "starts_on": date.today().strftime("%Y-%m-%d"),
                    "periodicity": "yearly",
                    "amount": 10,
                    "created_at_0": date.today().strftime("%Y-%m-%d"),
                    "created_at_1": "12:00",
                },
                zero_management_form_data("periods"),
            ),
        )
        self.assertRedirects(response, "/admin/user_subscriptions/subscription/")

        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(SubscriptionPeriod.objects.count(), 1)

    def test_admin_update(self):
        values = {"code": "yay", "title": "yay", "periodicity": "yearly", "amount": 10}

        subscription = Subscription.objects.create(user=self.user, **values)

        client = self.login()
        response = client.post(
            "/admin/user_subscriptions/subscription/%s/change/" % subscription.pk,
            merge_dicts(
                {
                    "created_at_0": date.today().strftime("%Y-%m-%d"),
                    "created_at_1": "12:00",
                    "starts_on": date.today().strftime("%Y-%m-%d"),
                    "user": self.user.pk,
                    **values,
                },
                zero_management_form_data("periods"),
            ),
        )
        self.assertRedirects(response, "/admin/user_subscriptions/subscription/")

        self.assertEqual(Subscription.objects.count(), 1)
        # Periods are NOT automatically created when updating subscriptions
        self.assertEqual(SubscriptionPeriod.objects.count(), 0)

    def test_unbound_amount_change(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
        )
        period = subscription.create_periods()[-1]
        period.create_line_item()

        self.assertEqual(period.line_item.amount, 60)

        subscription.amount = 100
        subscription.save()

        period.line_item.refresh_from_db()
        self.assertEqual(period.line_item.amount, 100)

    def test_ensure(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2018, 1, 1),
        )

        self.assertEqual(subscription.starts_on, date(2018, 1, 1))
        self.assertEqual(subscription.paid_until, date(2017, 12, 31))

        periods = subscription.create_periods()
        self.assertNotEqual(subscription.periods.count(), 0)

        # Unpaid
        periods[0].create_line_item()
        Payment.objects.create_pending(user=self.user, lineitems=[periods[0].line_item])
        # Unbound
        periods[1].create_line_item()

        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date.today(),
        )

        # Pending periods have been removed
        self.assertEqual(subscription.periods.count(), 0)

        # Pay for a period...
        self.pay_period(subscription.create_periods()[-1])

        subscription.refresh_from_db()
        paid_until = subscription.paid_until
        self.assertTrue(paid_until > date.today() + timedelta(days=25))

        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="yearly",
            amount=720,
            starts_on=date.today() + timedelta(days=10),
        )

        self.assertEqual(subscription.periodicity, "yearly")
        # starts_on is automatically moved after the paid_until value
        self.assertTrue(subscription.starts_on, paid_until + timedelta(days=1))

    def test_ensure_twice(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
        )
        self.pay_period(subscription.create_periods()[0])

        # And second request comes in...
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
        )

        # Test that the second, equivalent request didn't move the start, and
        # that -- for now -- only one period exists
        self.assertEqual(
            list(subscription.create_periods(until=subscription.starts_on)), []
        )
        self.assertEqual(subscription.periods.count(), 1)
        self.assertEqual(subscription.starts_on, date.today())

    def test_ensure_with_change(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2040, 1, 1),
        )
        period = subscription.create_periods(until=subscription.starts_on)[0]
        self.pay_period(period)

        period.ends_on = date(2040, 1, 15)
        period.save()

        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="yearly",
            amount=900,
            starts_on=period.ends_on,
        )

        # Without updating subscription.paid_until, simply editing a period
        # does not do anything
        self.assertEqual(subscription.starts_on, date(2040, 2, 1))
        self.assertEqual(subscription.periodicity, "yearly")
        self.assertEqual(subscription.amount, 900)

        # Create the next period and pay for it...
        period = subscription.create_periods(until=subscription.starts_on)[0]
        self.pay_period(period)

        period.ends_on = date(2040, 2, 15)
        period.save()

        # ... but this makes it different!
        subscription.update_paid_until()
        self.assertEqual(subscription.paid_until, date(2040, 2, 15))

        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="yearly",
            amount=900,
            starts_on=period.ends_on,
        )

        self.assertEqual(subscription.starts_on, date(2040, 2, 16))
        self.assertEqual(subscription.periodicity, "yearly")
        self.assertEqual(subscription.amount, 900)

    def test_ensure_direct_change(self):
        Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
        )
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="yearly",
            amount=900,
        )

        # Second one wins, but starting point is still today (as no periods
        # were paid for)
        self.assertEqual(subscription.starts_on, date.today())
        self.assertEqual(subscription.periodicity, "yearly")
        self.assertEqual(subscription.amount, 900)

    def test_ensure_future(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2040, 1, 1),
        )
        self.assertEqual(subscription.paid_until, date(2039, 12, 31))

        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="yearly",
            amount=900,
            starts_on=date(2040, 1, 1),
        )

        self.assertEqual(subscription.starts_on, date(2040, 1, 1))
        self.assertEqual(subscription.periodicity, "yearly")

    def test_update_paid_until(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2018, 1, 1),
        )

        period = subscription.create_periods()[0]
        period.create_line_item()
        Payment.objects.create_pending(user=self.user)

        # No post_save signal:
        Payment.objects.update(charged_at=timezone.now())

        subscription.update_paid_until(save=False)
        self.assertEqual(subscription.paid_until, date(2018, 1, 31))
        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, date(2017, 12, 31))

        Payment.objects.get().save()
        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, date(2018, 1, 31))

    def test_cancel(self):
        subscription = Subscription.objects.ensure(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2018, 1, 1),
        )
        self.assertEqual(len(subscription.create_periods(until=date(2018, 4, 1))), 4)
        subscription.cancel()
        self.assertEqual(subscription.periods.count(), 0)
        self.assertEqual(len(subscription.create_periods(until=date(2018, 4, 1))), 0)

    def test_admin_create_manual_periodicity(self):
        client = self.login()
        response = client.post(
            "/admin/user_subscriptions/subscription/add/",
            merge_dicts(
                {
                    "user": self.user.pk,
                    "code": "yay",
                    "title": "yay",
                    "starts_on": date.today().strftime("%Y-%m-%d"),
                    "periodicity": "manually",
                    "amount": 10,
                    "created_at_0": date.today().strftime("%Y-%m-%d"),
                    "created_at_1": "12:00",
                },
                zero_management_form_data("periods"),
            ),
            follow=True,
        )
        # self.assertRedirects(response, "/admin/user_subscriptions/subscription/")

        messages = [str(m) for m in response.context["messages"]]
        self.assertEqual(messages[0], "Unknown periodicity 'manually'")
        self.assertEqual(len(messages), 2)

        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(SubscriptionPeriod.objects.count(), 0)
