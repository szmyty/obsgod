package commands

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/muesli/coral"
)

type presentation struct{ verbose, noColor bool }

func diagnosticPrefix(noColor, terminal bool) string {
	if terminal && !noColor && os.Getenv("NO_COLOR") == "" && os.Getenv("TERM") != "" && os.Getenv("TERM") != "dumb" {
		return "\x1b[36mobsgod diagnostic\x1b[0m"
	}
	return "obsgod diagnostic"
}

func diagnosticMetadata(cmd *coral.Command, options presentation, stage string) {
	if !options.verbose {
		return
	}
	terminal := false
	if file, ok := cmd.ErrOrStderr().(*os.File); ok {
		if state, err := file.Stat(); err == nil {
			terminal = state.Mode()&os.ModeCharDevice != 0
		}
	}
	// Command names come from the static tree. Deliberately omit user arguments,
	// connection addresses, file paths, profile names, environment and payloads.
	fmt.Fprintf(cmd.ErrOrStderr(), "%s: command=%s stage=%s\n", diagnosticPrefix(options.noColor, terminal), cmd.CommandPath(), stage)
}

func newReferenceCommand() *coral.Command {
	return &coral.Command{Use: "reference", Short: "Generate a deterministic offline Markdown command reference", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		var text strings.Builder
		if err := writeReference(cmd.Root(), &text); err != nil {
			return err
		}
		_, err := io.WriteString(cmd.OutOrStdout(), strings.TrimRight(text.String(), "\n")+"\n")
		return err
	}}
}

func writeReference(root *coral.Command, output io.Writer) error {
	root.InitDefaultHelpCmd()
	root.InitDefaultHelpFlag()
	if _, err := fmt.Fprint(output, "# obsgod command reference\n\nGenerated from the current command tree. Built-in defaults are shown; use `config show` for effective settings. Commands marked JSON keep that format. Other commands retain their existing human output.\n\n"); err != nil {
		return err
	}
	var walk func(*coral.Command) error
	walk = func(command *coral.Command) error {
		if command.Hidden {
			return nil
		}
		if _, err := fmt.Fprintf(output, "## %s\n\n%s\n\n```text\n%s\n```\n\n", command.CommandPath(), command.Short, command.UseLine()); err != nil {
			return err
		}
		if len(command.Aliases) > 0 {
			if _, err := fmt.Fprintf(output, "Aliases: %s.\n\n", strings.Join(command.Aliases, ", ")); err != nil {
				return err
			}
		}
		if command.Example != "" {
			if _, err := fmt.Fprintf(output, "```sh\n%s\n```\n\n", command.Example); err != nil {
				return err
			}
		}
		if flags := command.LocalFlags().FlagUsages(); flags != "" {
			if _, err := fmt.Fprintf(output, "```text\n%s```\n\n", flags); err != nil {
				return err
			}
		}
		for _, child := range command.Commands() {
			if err := walk(child); err != nil {
				return err
			}
		}
		return nil
	}
	return walk(root)
}
