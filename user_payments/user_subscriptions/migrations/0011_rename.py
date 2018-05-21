from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("user_subscriptions", "0010_auto_20180518_1702")]

    operations = [
        migrations.RenameField(
            model_name="subscription", old_name="starts_at", new_name="starts_on"
        ),
        migrations.RenameField(
            model_name="subscription", old_name="ends_at", new_name="ends_on"
        ),
        migrations.RenameField(
            model_name="subscriptionperiod", old_name="starts_at", new_name="starts_on"
        ),
        migrations.RenameField(
            model_name="subscriptionperiod", old_name="ends_at", new_name="ends_on"
        ),
    ]
