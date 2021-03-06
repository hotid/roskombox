# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2016-08-26 13:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0025_auto_20160401_0956'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablelink',
            name='code',
            field=models.IntegerField(default=0, verbose_name='Код ответа'),
        ),
        migrations.AddField(
            model_name='availablelink',
            name='content',
            field=models.BinaryField(blank=True, default=b'', verbose_name='Содержимое'),
        ),
    ]
