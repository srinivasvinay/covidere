# Generated by Django 3.0.4 on 2020-03-26 09:58

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Shop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('address', models.CharField(max_length=100)),
                ('zipcode', models.CharField(max_length=10)),
                ('city', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('homepage', models.URLField()),
                ('phone', models.CharField(max_length=20)),
                ('mobilepay', models.CharField(max_length=8)),
                ('contact', models.CharField(max_length=50)),
            ],
        ),
    ]