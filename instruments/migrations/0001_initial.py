from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Instrument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32, unique=True)),
                ("exchange", models.CharField(blank=True, max_length=16)),
                ("name", models.CharField(max_length=160)),
                ("sector", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["symbol"]},
        ),
        migrations.CreateModel(
            name="PriceBar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField()),
                ("open", models.DecimalField(decimal_places=6, max_digits=18)),
                ("high", models.DecimalField(decimal_places=6, max_digits=18)),
                ("low", models.DecimalField(decimal_places=6, max_digits=18)),
                ("close", models.DecimalField(decimal_places=6, max_digits=18)),
                ("volume", models.PositiveBigIntegerField(default=0)),
                ("interval", models.CharField(choices=[("1m", "1 minute"), ("5m", "5 minutes"), ("1d", "1 day")], default="1d", max_length=2)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_bars", to="instruments.instrument")),
            ],
            options={"ordering": ["-timestamp"]},
        ),
        migrations.AddConstraint(model_name="pricebar", constraint=models.UniqueConstraint(fields=("instrument", "timestamp", "interval"), name="uniq_instrument_bar_interval")),
        migrations.AddIndex(model_name="instrument", index=models.Index(fields=["exchange", "symbol"], name="instr_exchange_symbol_idx")),
        migrations.AddIndex(model_name="pricebar", index=models.Index(fields=["instrument", "timestamp"], name="price_instr_timestamp_idx")),
        migrations.AddIndex(model_name="pricebar", index=models.Index(fields=["instrument", "interval", "timestamp"], name="price_instr_int_time_idx")),
    ]
