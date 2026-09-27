from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("instruments", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Watchlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watchlists", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="WatchlistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watchlist_items", to="instruments.instrument")),
                ("watchlist", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="watchlists.watchlist")),
            ],
            options={"ordering": ["-added_at"]},
        ),
        migrations.AddConstraint(model_name="watchlist", constraint=models.UniqueConstraint(fields=("user", "name"), name="uniq_watchlist_name_per_user")),
        migrations.AddConstraint(model_name="watchlistitem", constraint=models.UniqueConstraint(fields=("watchlist", "instrument"), name="uniq_instrument_per_watchlist")),
        migrations.AddIndex(model_name="watchlistitem", index=models.Index(fields=["watchlist", "added_at"], name="watchlist_added_idx")),
    ]
