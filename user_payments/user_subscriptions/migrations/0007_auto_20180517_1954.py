# Generated by Django 2.0.5 on 2018-05-17 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("user_subscriptions", "0006_auto_20180517_0932")]

    operations = [
        migrations.AlterField(
            model_name="subscription",
            name="paid_until",
            field=models.DateTimeField(blank=True, verbose_name="paid until"),
        )
    ]