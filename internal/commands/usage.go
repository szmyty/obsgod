package commands

import "github.com/muesli/coral"

// Preserve canonical commands while supplying discoverable aliases and precise
// argument validation across the legacy tree. New commands retain explicit Args.
func auditCommandUsage(root *coral.Command) {
	root.Example = "  obsgod version\n  obsgod config show --json\n  obsgod stream status --json"
	var walk func(*coral.Command)
	walk = func(command *coral.Command) {
		switch command.CommandPath() {
		case "obsgod scene":
			command.Example = "  obsgod scene list\n  obsgod scene set Game"
		case "obsgod scene current":
			command.Aliases = []string{"set"}
			command.Use = "current NAME..."
			command.Args = coral.MinimumNArgs(1)
		case "obsgod scene preview", "obsgod scene switch", "obsgod profile set", "obsgod scenecollection set":
			command.Use = command.Name() + " NAME..."
			command.Args = coral.MinimumNArgs(1)
		case "obsgod scenecollection":
			command.Aliases = []string{"scene-collection"}
		case "obsgod sceneitem":
			command.Aliases = []string{"scene-item"}
		case "obsgod replaybuffer":
			command.Aliases = []string{"replay-buffer"}
		case "obsgod virtualcam":
			command.Aliases = []string{"virtual-camera"}
		case "obsgod studiomode":
			command.Aliases = []string{"studio-mode"}
		case "obsgod label text":
			command.Use = "text SOURCE TEXT..."
			command.Args = coral.MinimumNArgs(2)
		case "obsgod label countdown":
			command.Use = "countdown SOURCE DURATION"
			command.Args = coral.ExactArgs(2)
			command.Example = "  obsgod label countdown Countdown 30s"
			command.Short = "Update a text label with a cancellable duration countdown (for example 30s)"
		case "obsgod source toggle-mute":
			command.Use = "toggle-mute NAME..."
			command.Args = coral.MinimumNArgs(1)
		case "obsgod sceneitem list":
			command.Use = "list SCENE"
			command.Args = coral.ExactArgs(1)
		case "obsgod sceneitem toggle", "obsgod sceneitem show", "obsgod sceneitem hide", "obsgod sceneitem visible", "obsgod sceneitem center":
			command.Use = command.Name() + " SCENE ITEM..."
			command.Args = coral.MinimumNArgs(2)
		}
		if command.Runnable() && command.Args == nil {
			command.Args = coral.NoArgs
		}
		for _, child := range command.Commands() {
			walk(child)
		}
	}
	walk(root)
}
