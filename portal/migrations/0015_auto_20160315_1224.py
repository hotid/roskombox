# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-03-15 09:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0014_auto_20160315_1051'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scan',
            name='state',
            field=models.CharField(default='started', max_length=15, verbose_name='Статус'),
        ),
    ]
