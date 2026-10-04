import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Toploader in the bar: a Poké Ball and the collection's value.
//
// The value comes from `toploader summary`, which reads the collection with
// the prices saved by the app (no network) and prints JSON. Left click opens
// Toploader in a terminal, or focuses it when it is already open.
BarWidget {
  id: root
  moduleName: "smerlini.toploader"

  readonly property string pokeball: "\uDB81\uDC1D"  // nf-md-pokeball (U+F041D)
  readonly property string command: Quickshell.env("HOME") + "/.local/bin/toploader"
  readonly property bool showValue: setting("showValue", true) === true
  readonly property int refreshMinutes: Math.max(1, Number(setting("refreshMinutes", 5)) || 5)

  property var summary: null
  property bool failed: false

  function refresh() {
    if (!summaryProc.running) summaryProc.running = true
  }

  function openApp() {
    if (!root.bar) return
    root.bar.run("omarchy-launch-or-focus-tui --app-id=org.omarchy.toploader " + root.command)
  }

  function applySummary(text) {
    try {
      root.summary = JSON.parse(text)
      root.failed = false
    } catch (e) {
      root.failed = true
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: summaryProc
    command: [root.command, "summary"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applySummary(text)
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.failed = true
    }
  }

  Timer {
    interval: root.refreshMinutes * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.showValue && root.summary
      ? root.pokeball + "  " + root.summary.short
      : root.pokeball
    dimmed: root.failed
    tooltipText: root.failed
      ? "Toploader: couldn't read the collection (is ~/.local/bin/toploader installed?)"
      : root.summary
        ? "Toploader · " + root.summary.copies + " cards (" + root.summary.unique
          + " unique) · " + root.summary.text
        : "Toploader"

    onPressed: function(b) {
      if (b === Qt.MiddleButton) root.refresh()
      else root.openApp()
    }
  }
}
