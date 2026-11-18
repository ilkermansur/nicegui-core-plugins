from nicegui import run, ui

from ngui import NguiError
from ngui.loader import read_manifests
from ngui.roles import ROLE_ORDER

ACTIONS = {"add", "remove", "update", "rollback", "enable", "disable", "use"}
COLUMNS = ("name", "source", "role", "commit", "status")

GRID = "minmax(180px, 2fr) repeat(3, auto) minmax(120px, 1fr) auto"
CSS = """
.ngui-store-scroll { width: 100%; overflow-x: auto; }
.ngui-store-scroll > .nicegui-grid { gap: 8px 16px; align-items: center; min-width: 760px; }
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


class StorePage:
    def __init__(self, ctx):
        self.ctx, self.t, self.theme = ctx, ctx.t, ctx.role("theme")
        self.manager = ctx.kernel.manager
        self.controls = []
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
        busy = [c for c in self.controls if c.enabled]
        self._lock(busy, True)
        try:
            err = await run.io_bound(run_action, self.manager, action, *args)
        except BaseException:
            self._lock(busy, False)
            raise
        if err:
            self._lock(busy, False)
            ui.notify(self.ctx.i18n.t("core", err[0], **err[1]), type="negative", multi_line=True)
            return
        ui.notify(self.t("restarting"), type="positive")
        ui.timer(0.8, self.ctx.kernel.restart, once=True)

    def _lock(self, controls, locked: bool) -> None:
        self.locked = self.spinner.visible = locked
        for c in controls:
            c.set_enabled(not locked)

    async def purge(self, pid: str) -> None:
        if await self._confirm("confirm.purge", id=pid):
            self.ctx.role("storage").purge(pid)
            ui.notify(self.t("purged", id=pid), type="positive")

    def render(self) -> None:
        cfg = self.ctx.kernel.home.load_config()
        self.manifests = read_manifests(self.ctx.kernel.home, cfg)[0]
        self.lang = self.ctx.i18n.current_lang()
        self.rows = self.manager.status()
        self.theme.page_header(self.t("title"), self.t("description"))
        self._installed()
        self._catalog()
        self._roles(cfg)

    def _name(self, pid: str) -> str:
        m = self.manifests.get(pid)
        return (m.name.get(self.lang) or pid) if m else pid

    def _installed(self) -> None:
        def actions():
            self.spinner = ui.spinner(size="1.25em")
            self.spinner.visible = False
            if any(r.source == "core" for r in self.rows):
                self._button("update.core", lambda: self.act("update", "core"))

        with self.theme.card(self.t("installed"), actions).classes("w-full"):
            with ui.element("div").classes("ngui-store-scroll"), ui.grid(columns=GRID):
                for col in COLUMNS:
                    ui.label(self.t(f"col.{col}")).classes("ngui-store-head")
                ui.label()
                for r in self.rows:
                    self._row(r)

    def _row(self, r) -> None:
        with ui.column().classes("gap-0"):
            ui.label(self._name(r.id))
            ui.label(r.id).classes("ngui-store-id")
        ui.label(r.source)
        ui.label(r.role)
        ui.label(r.commit[:7])
        if r.problem:
            ui.label(r.problem).classes("ngui-tone-danger")
        else:
            ui.label(self.t("status.ok")).classes("ngui-tone-success")
        with ui.row().classes("gap-1 no-wrap justify-end"):
            if not r.role:
                key = "disable" if r.enabled else "enable"
                self._button(key, lambda r=r, key=key: self.act(key, r.id))
            if r.source == "repo":
                self._button("update", lambda r=r: self.act("update", r.id))
                self._button("rollback", lambda r=r: self.act("rollback", r.id, confirm="confirm.rollback"))
                if not r.role:
                    self._button("remove", lambda r=r: self.act("remove", r.id, confirm="confirm.remove"))
            self._button("purge", lambda r=r: self.purge(r.id))

    def _catalog(self) -> None:
        with self.theme.card(self.t("catalog")).classes("w-full"):
            box = ui.column().classes("w-full gap-2")
            with box:
                ui.spinner(size="1.25em")
            with ui.row().classes("w-full items-center no-wrap"):
                url = ui.input(self.t("install.url")).classes("grow")
                self._button("install", lambda: url.value.strip() and self.act("add", url.value.strip()))

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
                        btn.set_enabled(e.id not in installed and not self.locked)

        ui.timer(0, fill, once=True)

    def _roles(self, cfg) -> None:
        with self.theme.card(self.t("roles")).classes("w-full"):
            with ui.grid(columns="repeat(auto-fill, minmax(220px, 1fr))").classes("w-full"):
                for role in ROLE_ORDER:
                    options = {pid: self._name(pid) for pid, m in self.manifests.items() if m.provides == role}
                    self.controls.append(ui.select(options, label=role, value=cfg.roles.get(role),
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
