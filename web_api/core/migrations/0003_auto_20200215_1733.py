# Generated by Django 3.0.3 on 2020-02-15 17:33

import uuid

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_githubevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("github_id", models.IntegerField(unique=True)),
                ("github_account_id", models.IntegerField(unique=True)),
                ("github_account_login", models.CharField(max_length=255, unique=True)),
                (
                    "github_account_type",
                    models.CharField(
                        choices=[("User", "User"), ("Organization", "Organization")],
                        max_length=255,
                    ),
                ),
                (
                    "payload",
                    django.contrib.postgres.fields.jsonb.JSONField(default=dict),
                ),
            ],
            options={"db_table": "account",},
        ),
        migrations.AlterField(
            model_name="user", name="github_id", field=models.IntegerField(unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="github_login",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.CreateModel(
            name="AccountMembership",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="core.Account",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="core.User",
                    ),
                ),
            ],
            options={"db_table": "account_membership",},
        ),
    ]
