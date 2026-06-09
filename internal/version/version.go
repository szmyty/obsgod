package version

const Name = "obsgod"

func Display(buildVersion string) string {
	if buildVersion == "" {
		return "dev"
	}
	return buildVersion
}

func UserAgent(buildVersion string) string {
	userAgent := Name
	if buildVersion != "" {
		userAgent += "/" + buildVersion
	}
	return userAgent
}
