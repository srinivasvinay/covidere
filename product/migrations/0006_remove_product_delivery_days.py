# Generated by Django 3.0.4 on 2020-05-01 06:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0005_auto_20200428_0934'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='delivery_days',
        ),
    ]
