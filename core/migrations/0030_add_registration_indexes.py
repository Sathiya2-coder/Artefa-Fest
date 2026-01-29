# Generated migration to add performance indexes to Registration model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_alter_registration_register_number'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='registration',
            options={'ordering': ['-registered_at']},
        ),
        migrations.AddIndex(
            model_name='registration',
            index=models.Index(fields=['register_number'], name='core_regist_register_idx'),
        ),
        migrations.AddIndex(
            model_name='registration',
            index=models.Index(fields=['event', 'register_number'], name='core_regist_event_reg_idx'),
        ),
        migrations.AddIndex(
            model_name='registration',
            index=models.Index(fields=['event', 'is_team_lead'], name='core_regist_event_lead_idx'),
        ),
        migrations.AddIndex(
            model_name='registration',
            index=models.Index(fields=['-registered_at'], name='core_regist_date_idx'),
        ),
    ]
