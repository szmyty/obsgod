package commands

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/szmyty/obsgod/internal/obs"
)

func parseCountdownDuration(value string) (time.Duration, error) {
	duration, err := time.ParseDuration(value)
	if err != nil || duration <= 0 || duration > 24*time.Hour {
		return 0, errors.New("countdown duration must be positive, at most 24h, with units such as 30s or 2m")
	}
	return duration, nil
}

func countdown(ctx context.Context, service obs.Service, label string, duration time.Duration) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	until := time.Now().Add(duration).Add(time.Second)

	c := time.NewTicker(time.Second)
	defer c.Stop()
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-c.C:
		}
		if err := ctx.Err(); err != nil {
			return err
		}
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
