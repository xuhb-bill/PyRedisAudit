from packaging import version

class VersionChecker:
    """
    Utility to compare Redis versions.
    """
    @staticmethod
    def is_supported(target_version, introduced_version):
        if not introduced_version:
            return True
        return version.parse(target_version) >= version.parse(introduced_version)

    @staticmethod
    def is_deprecated(target_version, deprecated_version):
        if not deprecated_version:
            return False
        return version.parse(target_version) >= version.parse(deprecated_version)
