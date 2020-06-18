# Generated by Django 3.0.3 on 2020-06-17 12:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_auto_20200613_2012"),
    ]

    operations = [
        migrations.AddField(
            model_name="stripecustomerinformation",
            name="plan_interval",
            field=models.CharField(
                help_text="The frequency at which a subscription is billed. One of `day`, `week`, `month` or `year`.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="stripecustomerinformation",
            name="plan_interval_count",
            field=models.IntegerField(
                help_text="The number of intervals (specified in the `interval` attribute) between subscription billings. For example, `interval=month` and `interval_count=3` bills every 3 months.",
                null=True,
            ),
        ),
    ]
