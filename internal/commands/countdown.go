package commands

import (
	"fmt"
	"time"

	"github.com/szmyty/obsgod/internal/obs"
)

func parseCountdownDuration(value string) (time.Duration, error) {
	return time.ParseDuration(value)
}

func countdown(service obs.Service, label string, duration time.Duration) error {
	until := time.Now().Add(duration).Add(time.Second)

	c := time.Tick(time.Second)
	for range c {
		remaining := time.Until(until)
		if remaining < 0 {
			remaining = 0
		}
		if err := service.SetLabelText(label, fmtDuration(remaining)); err != nil {
			return err
		}

		if time.Now().After(until) {
			break
		}
	}

	return nil
}

func fmtDuration(d time.Duration) string {
	d = d.Round(time.Second)
	m := d % time.Hour / time.Minute
	s := d % time.Minute / time.Second
	return fmt.Sprintf("%02d:%02d", m, s)
}
