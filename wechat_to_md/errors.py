"""Custom exception hierarchy for wechat_to_md."""


class WechatToMdError(Exception):
    """Base exception for all errors in this package."""


class CaptchaError(WechatToMdError):
    """WeChat shows a CAPTCHA/verification page instead of article content."""


class NetworkError(WechatToMdError):
    """Network request failed after all retries."""


class ParseError(WechatToMdError):
    """HTML content cannot be parsed into expected structure."""
