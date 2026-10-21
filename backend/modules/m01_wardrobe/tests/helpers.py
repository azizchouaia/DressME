import base64
import io


def png_b64(color=(31, 42, 68), size=(64, 64), data_url=False) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}" if data_url else b64
