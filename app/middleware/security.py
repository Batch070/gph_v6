from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Standard security headers for production
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # We allow a relatively open CSP here because the app loads inline scripts/styles
        # and external resources (like Razorpay, FontAwesome, Google Fonts).
        # In a strict production environment, nonces or hashes should be used.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com https://kit.fontawesome.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://ka-f.fontawesome.com; "
            "img-src 'self' data: https://checkout.razorpay.com https://badges.razorpay.com; "
            "frame-src https://api.razorpay.com; "
            "connect-src 'self' https://api.razorpay.com https://ka-f.fontawesome.com wss:;"
        )
        
        return response
