# Generated by Django 2.0.5 on 2018-05-31 19:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_auto_20180529_1526'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providerauthentication',
            name='provider_resource_name',
            field=models.TextField(unique=True),
        ),
    ]
