from nicegui import run, ui

from ngui import NguiError
from ngui.config import CORE_KEY
from ngui.loader import read_manifests
from ngui.manifest import localized
from ngui.roles import ROLE_ORDER

ACTIONS = {"add", "remove", "update", "rollback", "enable", "disable", "use"}
COLUMNS = ("name", "source", "role", "commit", "status")

ICONS = {"enable": "toggle_off", "disable": "toggle_on", "update": "system_update",
         "rollback": "history", "remove": "delete", "purge": "delete_sweep"}
DANGER = {"remove", "purge"}
CORE_ACTIONS = {"update.core": ("update", None), "rollback.core": ("rollback", "confirm.rollback")}
GRID = "minmax(112px, 2fr) repeat(3, auto) minmax(64px, 1fr) auto"
CSS = """
.ngui-store-scroll { width: 100%; max-width: 100%; min-width: 0; overflow-x: auto; }
.ngui-store-scroll > .nicegui-grid { gap: 8px 12px; align-items: center; }
.ngui-store-actions .q-btn { color: var(--ngui-muted); }
.ngui-store-actions .q-btn.ngui-store-danger { color: var(--ngui-danger); }
.ngui-store-head { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--ngui-muted); }
.ngui-store-id, .ngui-store-desc { font-size: 0.8125rem; color: var(--ngui-muted); }
.ngui-store-line { width: 100%; border-top: 1px solid var(--ngui-border); padding-top: 8px; }
"""


def run_action(manager, action: str, *args) -> tuple[str, dict] | None:
    """Run a manager action, then sync dependencies; a NguiError becomes (key, vars)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown store action: {action!r}")
    try:
        getattr(manager, action)(*args)
        manager.sync_deps()
    except NguiError as e:
        return e.key, e.vars
    return None


def role_options(manifests: dict, role: str, current: str | None, name) -> dict[str, str]:
    """Plugins that can fill `role`, plus the assigned one even if its manifest is unreadable."""
    options = {pid: name(pid) for pid, m in manifests.items() if m.provides == role}
    if current and current not in options:
        options[current] = current
    return options


def row_actions(row, self_id: str) -> list[str]:
    """The actions the installed table offers for a `PluginStatus` row, in display order."""
    acts = []
    if not row.role and row.id != self_id:  # disabling the store itself would lock the user out
        acts.append("disable" if row.enabled else "enable")
    if row.source == "repo":
        acts += ["update", "rollback"]
        if not row.role and row.id != self_id:
            acts.append("remove")
    return [*acts, "purge"]


def short_commit(row, lock: dict) -> str:
    """Core plugins have no lock entry of their own; they show the core-plugins repo commit."""
    entry = lock.get(CORE_KEY) if row.source == "core" else None
    return (entry.commit if entry else row.commit)[:7]


class StorePage:
    def __init__(self, ctx):
        self.ctx, self.t, self.theme = ctx, ctx.t, ctx.role("theme")
        self.manager = ctx.kernel.manager
        self.controls, self.off = [], []  # `off`: controls that stay disabled (installed catalog entries)
        self.spinner = None
        self.locked = False  # an action is running or succeeded and the app restarts

    def _button(self, key: str, on_click):
        btn = ui.button(self.t(key), on_click=on_click, color=None).props("flat dense no-caps")
        self.controls.append(btn)
        return btn

    async def _confirm(self, key: str, **vars) -> bool:
        with ui.dialog() as dialog, self.theme.card():
            ui.label(self.t(key, **vars))
            with ui.row().classes("w-full justify-end"):
                ui.button(self.t("cancel"), on_click=lambda: dialog.submit(False), color=None).props("flat no-caps")
                ui.button(self.t("confirm"), on_click=lambda: dialog.submit(True), color="negative").props("no-caps")
        ok = await dialog
        dialog.delete()
        return bool(ok)

    async def act(self, action: str, *args, confirm: str | None = None) -> None:
        if confirm and not await self._confirm(confirm, id=args[-1], role=args[0]):
            return
        if await self._guarded(run_action, self.manager, action, *args, hold=True):
            ui.notify(self.t("restarting"), type="positive")
            ui.timer(0.8, self.ctx.kernel.restart, once=True)

    async def _guarded(self, fn, *args, hold: bool = False) -> bool:
        """Run `fn` in a thread with the controls locked; notify a failure. `hold` keeps them locked on success."""
        self._lock(True)
        try:
            err = await run.io_bound(fn, *args)
            msg = err and self.ctx.i18n.t("core", err[0], **err[1])
        except Exception:
            self.ctx.log.exception("store: %s%r failed", getattr(fn, "__name__", fn), args)
            msg = self.t("error.unexpected")
        if msg or not hold:
            self._lock(False)
        if msg:
            ui.notify(msg, type="negative", multi_line=True)
        return not msg

    def _lock(self, locked: bool) -> None:
        self.locked = locked
        if self.spinner:
            self.spinner.visible = locked
        for c in self.controls:
            c.set_enabled(not locked and c not in self.off)

    async def install(self, url: str) -> None:
        if url := url.strip():
            await self.act("add", url, confirm="confirm.install")

    async def purge(self, pid: str) -> None:
        if await self._confirm("confirm.purge", id=pid) and await self._guarded(self.ctx.role("storage").purge, pid):
            ui.notify(self.t("purged", id=pid), type="positive")

    def render(self) -> None:
        cfg = self.ctx.kernel.home.load_config()
        self.manifests = read_manifests(self.ctx.kernel.home, cfg)[0]
        self.lang = self.ctx.i18n.current_lang()
        self.rows, self.lock = self.manager.status(), self.ctx.kernel.home.load_lock()
        self.theme.page_header(self.t("title"), self.t("description"))
        self._installed()
        self._catalog()
        self._roles(cfg)

    def _name(self, pid: str) -> str:
        m = self.manifests.get(pid)
        return (localized(m.name, self.lang) or pid) if m else pid

    def _installed(self) -> None:
        def actions():
            self.spinner = ui.spinner(size="1.25em")
            self.spinner.visible = False
            if any(r.source == "core" for r in self.rows):
                for key, (action, confirm) in CORE_ACTIONS.items():
                    self._button(key, lambda action=action, confirm=confirm: self.act(action, "core", confirm=confirm))

        with self.theme.card(self.t("installed"), actions).classes("w-full"):
            with ui.element("div").classes("ngui-store-scroll"), ui.grid(columns=GRID):
                for col in COLUMNS:
                    ui.label(self.t(f"col.{col}")).classes("ngui-store-head")
                ui.label()
                for r in self.rows:
                    self._row(r)

    def _row(self, r) -> None:
        m = self.manifests.get(r.id)
        with ui.column().classes("gap-0"):
            ui.label(self._name(r.id))
            if m and (desc := localized(m.description, self.lang)):
                ui.label(desc).classes("ngui-store-desc")
            ui.label(r.id).classes("ngui-store-id")
        ui.label(r.source)
        ui.label(r.role)
        ui.label(short_commit(r, self.lock))
        if r.problem:
            ui.label(r.problem).classes("ngui-tone-danger")
        else:
            ui.label(self.t("status.ok")).classes("ngui-tone-success")
        with ui.row().classes("ngui-store-actions gap-0 justify-end"):
            for key in row_actions(r, self.ctx.id):
                self._icon_button(key, lambda key=key, pid=r.id: self._row_action(key, pid))

    def _icon_button(self, key: str, on_click) -> None:
        label = self.t(key)
        btn = ui.button(icon=ICONS[key], on_click=on_click, color=None).props("flat dense round")
        btn.props["aria-label"] = label
        btn.classes("ngui-store-danger" if key in DANGER else "").tooltip(label)
        self.controls.append(btn)

    async def _row_action(self, key: str, pid: str) -> None:
        if key == "purge":
            await self.purge(pid)
        else:
            await self.act(key, pid, confirm=f"confirm.{key}" if key in ("remove", "rollback") else None)

    def _catalog(self) -> None:
        with self.theme.card(self.t("catalog")).classes("w-full"):
            box = ui.column().classes("w-full gap-2")
            with box:
                ui.spinner(size="1.25em")
            with ui.row().classes("w-full items-center no-wrap"):
                url = ui.input(self.t("install.url")).classes("grow")
                self._button("install", lambda: self.install(url.value))

        async def fill():
            entries = await run.io_bound(self.manager.catalog)
            installed = {r.id for r in self.rows}
            box.clear()
            with box:
                if not entries:
                    ui.label(self.t("catalog.empty")).classes("ngui-store-desc")
                for e in entries:
                    with ui.row().classes("ngui-store-line items-center no-wrap"):
                        with ui.column().classes("gap-0 grow"):
                            ui.label(e.id)
                            ui.label(e.description).classes("ngui-store-desc")
                        btn = self._button("install", lambda e=e: self.act("add", e.url))
                        if e.id in installed:
                            self.off.append(btn)
                        btn.set_enabled(not self.locked and e.id not in installed)

        ui.timer(0, fill, once=True)

    def _roles(self, cfg) -> None:
        with self.theme.card(self.t("roles")).classes("w-full"):
            with ui.grid(columns="repeat(auto-fill, minmax(220px, 1fr))").classes("w-full"):
                for role in ROLE_ORDER:
                    current = cfg.roles.get(role)
                    options = role_options(self.manifests, role, current, self._name)
                    self.controls.append(ui.select(options, label=role, value=current,
                                                   on_change=lambda e, role=role: self._use(e, role)))

    async def _use(self, e, role: str) -> None:
        current = self.ctx.kernel.home.load_config().roles.get(role)
        if self.locked or not e.value or e.value == current:
            return  # also where the revert below lands
        await self.act("use", role, e.value, confirm="confirm.role")
        if not self.locked:  # cancelled or failed: show the plugin that still fills the role
            e.sender.set_value(current)


def setup(ctx) -> None:
    ui.add_css(CSS, shared=True)

    @ctx.role("layout").page("/store", title=lambda: ctx.t("title"), icon="extension", permission="store.manage")
    def store_page():
        StorePage(ctx).render()
