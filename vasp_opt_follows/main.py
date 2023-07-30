import sys
from typing import List
import gi

from vasp_opt_follows.windows import AppWindow

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk, Gio, Gdk  # noqa


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='be.unamur.lct.vasp_opt_view')
        GLib.set_application_name('My Gtk Application')

        self.connect('open', self.on_open)
        self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)

    def do_activate(self):
        self.window = AppWindow(application=self, title='VASP optimization viewer')
        self.window.present()

    def on_open(self, app: Gtk.Application, files: List[Gio.File], n_files: int, hint):
        self.do_activate()  # Adding this because window may not have been created yet with this entry point
        for file in files:
            self.window.open_vasp_h5(file)


def main():
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == '__main__':
    main()
