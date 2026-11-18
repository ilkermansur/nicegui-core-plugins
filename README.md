# nicegui-core-plugins

ngui platformunun beş çekirdek plugin'ini barındıran repo. ngui çekirdeği yalnızca plugin yükler; depolama, kimlik doğrulama, tema, yerleşim ve mağaza işlevleri burada.

| id | rol | ne yapar |
|----|-----|----------|
| `storage-sqlite` | storage | Plugin başına anahtar-değer verisini SQLite'ta saklar |
| `auth-local` | auth | Yerel kullanıcı adı/parola ile giriş ve oturum yönetimi |
| `theme-default` | theme | Varsayılan renk ve görünüm teması |
| `layout-sidebar` | layout | Kenar çubuklu sayfa yerleşimi |
| `store` | - | Plugin mağazası: plugin'leri listeler, kurar ve kaldırır |

Plugin sözleşmesi: [CONTRACT.md](https://github.com/ilkermansur/nicegui-core/blob/main/CONTRACT.md)

## Yerel geliştirme

```bash
python3 -m venv .venv
.venv/bin/pip install -e /yol/n_gui[dev]
ngui link <id> <yol>     # örn. ngui link storage-sqlite ./storage-sqlite
.venv/bin/pytest -q
```
