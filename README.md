# nicegui-core-plugins

ngui platformunun beş çekirdek plugin'ini barındıran repo. ngui çekirdeği yalnızca plugin yükler; depolama, kimlik doğrulama, tema, yerleşim ve mağaza işlevleri burada.

| id | rol | ne yapar |
|----|-----|----------|
| `storage-sqlite` | storage | Plugin başına anahtar-değer verisini SQLite'ta saklar |
| `auth-local` | auth | Tek yerel kullanıcı ("Yönetici"), her izni verir; gerçek giriş ayrı bir auth plugin'inin işi |
| `theme-default` | theme | Açık/koyu mod, renk değişkenleri, kart/KPI/sayfa başlığı yardımcıları |
| `layout-sidebar` | layout | Üst bar, ikon menü, breadcrumb, ana sayfa; sayfa/menü kaydı |
| `store` | - | Kurulu plugin'ler, katalog, URL ile kurma, rol atama, güncelle/geri al |

Plugin sözleşmesi: [CONTRACT.md](https://github.com/ilkermansur/nicegui-core/blob/main/CONTRACT.md)

## Yerel geliştirme

```bash
python3 -m venv .venv
.venv/bin/pip install -e /yol/n_gui[dev]
ngui link <id> <yol>     # örn. ngui link storage-sqlite ./storage-sqlite
.venv/bin/pytest -q
```
