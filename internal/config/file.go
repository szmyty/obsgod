package config

import (
	"encoding/json"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
)

// Connection contains references to credentials, never inline credentials.
// Pointers preserve the distinction between an omitted field and an invalid zero.
type Connection struct {
	Host         *string `json:"host,omitempty"`
	Port         *uint32 `json:"port,omitempty"`
	PasswordEnv  string  `json:"password_env,omitempty"`
	PasswordFile string  `json:"password_file,omitempty"`
}

type File struct {
	Version        int                   `json:"version"`
	Connection     Connection            `json:"connection"`
	DefaultProfile string                `json:"default_profile,omitempty"`
	Profiles       map[string]Connection `json:"profiles,omitempty"`
}

type Options struct {
	Path         string
	Profile      string
	Host         *string
	Port         *uint32
	Password     *string
	PasswordFile string
}

// Resolved keeps credentials outside the public diagnostic representation.
type Resolved struct {
	Config         Config `json:"-"`
	File           string `json:"config_file"`
	Loaded         bool   `json:"file_loaded"`
	Profile        string `json:"connection_profile,omitempty"`
	Profiles       []string
	PasswordSource string
}

type Public struct {
	SchemaVersion      int      `json:"schema_version"`
	ConfigFile         string   `json:"config_file"`
	FileLoaded         bool     `json:"file_loaded"`
	ConnectionProfile  string   `json:"connection_profile,omitempty"`
	Profiles           []string `json:"profiles"`
	Host               string   `json:"host"`
	Port               uint32   `json:"port"`
	PasswordConfigured bool     `json:"password_configured"`
	PasswordSource     string   `json:"password_source"`
	OBSConnection      string   `json:"obs_connection"`
}

func (r Resolved) Public() Public {
	return Public{SchemaVersion: 1, ConfigFile: r.File, FileLoaded: r.Loaded,
		ConnectionProfile: r.Profile, Profiles: r.Profiles, Host: r.Config.Host,
		Port: r.Config.Port, PasswordConfigured: r.Config.Password != "",
		PasswordSource: r.PasswordSource, OBSConnection: "not_checked"}
}

var profileName = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`)
var environmentName = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// DefaultPath preserves the obsgod namespace through the display-name change.
// UserConfigDir honors XDG_CONFIG_HOME on Unix and the native equivalent elsewhere.
func DefaultPath() (string, error) {
	root, err := os.UserConfigDir()
	if err != nil || !filepath.IsAbs(root) {
		return "", errors.New("configuration directory is unavailable; set an absolute XDG_CONFIG_HOME or use --config")
	}
	return filepath.Join(root, "obsgod", "config.json"), nil
}

func ConfigPath(explicit string) (string, bool, error) {
	if explicit != "" {
		return explicit, true, nil
	}
	if value := os.Getenv("OBSGOD_CONFIG"); value != "" {
		return value, true, nil
	}
	path, err := DefaultPath()
	return path, false, err
}

// Resolve applies flags > environment > selected file profile > file defaults >
// caller defaults. It never connects to OBS or writes a file.
func Resolve(base Config, options Options) (Resolved, error) {
	path, required, err := ConfigPath(options.Path)
	if err != nil {
		return Resolved{}, err
	}
	result := Resolved{Config: base, File: path, Profiles: []string{}, PasswordSource: "none"}
	if base.Password != "" {
		result.PasswordSource = "caller"
	}
	document, loaded, err := loadFile(path, required)
	if err != nil {
		return Resolved{}, err
	}
	result.Loaded = loaded
	connection := document.Connection
	selected := options.Profile
	if selected == "" {
		selected = os.Getenv("OBSGOD_CONNECTION_PROFILE")
	}
	if selected == "" {
		selected = document.DefaultProfile
	}
	for name := range document.Profiles {
		result.Profiles = append(result.Profiles, name)
	}
	sort.Strings(result.Profiles)
	if selected != "" {
		profile, ok := document.Profiles[selected]
		if !profileName.MatchString(selected) || !ok {
			return Resolved{}, errors.New("connection profile is unavailable; use config profiles to list configured profiles")
		}
		connection = mergeConnection(connection, profile)
		result.Profile = selected
	}
	if connection.Host != nil {
		result.Config.Host = *connection.Host
	}
	if connection.Port != nil {
		result.Config.Port = *connection.Port
	}
	if value, ok := nonemptyEnv("OBSGOD_HOST", "OBS_HOST"); ok {
		result.Config.Host = value
	}
	if value, ok := nonemptyEnv("OBSGOD_PORT", "OBS_PORT"); ok && options.Port == nil {
		port, parseErr := strconv.ParseUint(value, 10, 32)
		if parseErr != nil {
			return Resolved{}, errors.New("OBS port environment value must be an integer from 1 to 65535")
		}
		result.Config.Port = uint32(port)
	}
	if options.Host != nil {
		result.Config.Host = *options.Host
	}
	if options.Port != nil {
		result.Config.Port = *options.Port
	}
	if err := validateAddress(result.Config); err != nil {
		return Resolved{}, err
	}
	password, source, err := resolvePassword(base.Password, path, connection, options)
	if err != nil {
		return Resolved{}, err
	}
	result.Config.Password, result.PasswordSource = password, source
	return result, nil
}

// ProfileNames is deliberately independent of the currently selected profile
// and its secrets, so it can help recover a missing selection or credential.
func ProfileNames(explicit string) ([]string, error) {
	path, required, err := ConfigPath(explicit)
	if err != nil {
		return nil, err
	}
	document, _, err := loadFile(path, required)
	if err != nil {
		return nil, err
	}
	names := []string{}
	for name := range document.Profiles {
		names = append(names, name)
	}
	sort.Strings(names)
	return names, nil
}

func nonemptyEnv(keys ...string) (string, bool) {
	for _, key := range keys {
		if value := os.Getenv(key); value != "" {
			return value, true
		}
	}
	return "", false
}

func mergeConnection(base, selected Connection) Connection {
	if selected.Host != nil {
		base.Host = selected.Host
	}
	if selected.Port != nil {
		base.Port = selected.Port
	}
	if selected.PasswordEnv != "" || selected.PasswordFile != "" {
		base.PasswordEnv, base.PasswordFile = selected.PasswordEnv, selected.PasswordFile
	}
	return base
}

func validateAddress(cfg Config) error {
	if cfg.Port == 0 || cfg.Port > 65535 {
		return errors.New("OBS port must be from 1 to 65535; correct --port, the environment or config file")
	}
	if cfg.Host == "" || strings.ContainsAny(cfg.Host, "/\\@?# \t\r\n\x00") {
		return errors.New("OBS host must be a hostname or IP address without a URL, credentials or whitespace")
	}
	for _, character := range cfg.Host {
		if character < 32 || character == 127 {
			return errors.New("OBS host contains unsupported characters")
		}
	}
	if strings.ContainsAny(cfg.Host, ":[]") && !(strings.HasPrefix(cfg.Host, "[") && strings.HasSuffix(cfg.Host, "]") && net.ParseIP(strings.TrimSuffix(strings.TrimPrefix(cfg.Host, "["), "]")) != nil) {
		return errors.New("set OBS host and port separately; IPv6 hosts must be enclosed in brackets")
	}
	return nil
}

func loadFile(path string, required bool) (File, bool, error) {
	data, err := readRegular(path, 1<<20, false)
	if errors.Is(err, os.ErrNotExist) && !required {
		return File{}, false, nil
	}
	if err != nil {
		return File{}, false, errors.New("cannot read OBS configuration; use config path and check the regular file and permissions")
	}
	var document File
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&document) != nil || decoder.Decode(new(any)) != io.EOF {
		return File{}, false, errors.New("invalid OBS configuration JSON; use version 1 schema and credential references, never inline passwords")
	}
	if document.Version != 1 {
		return File{}, false, errors.New("unsupported OBS configuration version; expected version 1")
	}
	if err := validateConnection(document.Connection); err != nil {
		return File{}, false, err
	}
	if document.DefaultProfile != "" && !profileName.MatchString(document.DefaultProfile) {
		return File{}, false, errors.New("default connection profile has an invalid name")
	}
	for name, connection := range document.Profiles {
		if !profileName.MatchString(name) {
			return File{}, false, errors.New("connection profile names must use 1–64 letters, digits, periods, underscores or hyphens")
		}
		if err := validateConnection(connection); err != nil {
			return File{}, false, err
		}
	}
	return document, true, nil
}

func validateConnection(connection Connection) error {
	if connection.PasswordEnv != "" && connection.PasswordFile != "" {
		return errors.New("each connection must choose password_env or password_file, not both")
	}
	if connection.PasswordEnv != "" && !environmentName.MatchString(connection.PasswordEnv) {
		return errors.New("password_env must name one environment variable")
	}
	return nil
}

func resolvePassword(base, configPath string, connection Connection, options Options) (string, string, error) {
	if options.Password != nil {
		return *options.Password, "flag", nil
	}
	if options.PasswordFile != "" {
		return passwordFile(options.PasswordFile)
	}
	for _, name := range []string{"OBSGOD_PASSWORD", "OBS_PASSWORD"} {
		if value, exists := os.LookupEnv(name); exists {
			return value, "environment", nil
		}
	}
	if path, ok := nonemptyEnv("OBSGOD_PASSWORD_FILE", "OBS_PASSWORD_FILE"); ok {
		return passwordFile(path)
	}
	if connection.PasswordEnv != "" {
		value, exists := os.LookupEnv(connection.PasswordEnv)
		if !exists {
			return "", "", errors.New("password_env reference is unset; set the referenced variable or use --password-file")
		}
		return value, "environment_reference", nil
	}
	if connection.PasswordFile != "" {
		path := connection.PasswordFile
		if !filepath.IsAbs(path) {
			path = filepath.Join(filepath.Dir(configPath), path)
		}
		return passwordFile(path)
	}
	if base != "" {
		return base, "caller", nil
	}
	return "", "none", nil
}

func passwordFile(path string) (string, string, error) {
	data, err := readRegular(path, 16<<10, true)
	if err != nil {
		return "", "", errors.New("cannot read password file; use a regular non-symlink file readable only by its owner (chmod 600)")
	}
	password := strings.TrimSuffix(strings.TrimSuffix(string(data), "\n"), "\r")
	if password == "" || strings.ContainsAny(password, "\r\n\x00") {
		return "", "", errors.New("password file must contain one nonempty line")
	}
	return password, "private_file", nil
}

func readRegular(path string, limit int64, private bool) ([]byte, error) {
	before, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if !before.Mode().IsRegular() || unsafePermissions(before.Mode(), private) {
		return nil, errors.New("unsafe file")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	after, err := file.Stat()
	if err != nil || !os.SameFile(before, after) || !after.Mode().IsRegular() || after.Size() > limit || unsafePermissions(after.Mode(), private) {
		return nil, errors.New("unsafe or oversized file")
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil || int64(len(data)) > limit {
		return nil, errors.New("cannot read bounded file")
	}
	return data, nil
}

func unsafePermissions(mode os.FileMode, private bool) bool {
	if runtime.GOOS == "windows" {
		return false // POSIX mode bits do not establish Windows ACL permissions.
	}
	return mode.Perm()&0o022 != 0 || (private && mode.Perm()&0o077 != 0)
}
