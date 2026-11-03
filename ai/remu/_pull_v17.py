"""Download one Kaggle notebook version without printing credentials."""

from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

OUT = Path(r"C:\Users\NADHIR\Desktop\Dressme\avatar_studio\web\garments\saved\auto_test\kernel_v17")
OUT.mkdir(parents=True, exist_ok=True)

api = KaggleApi()
api.authenticate()
with api.build_kaggle_client() as client:
    request = ApiGetKernelRequest()
    request.user_name = "nadhirmaamar"
    request.kernel_slug = "dressme-high-res-clothes"
    current = client.kernels.kernels_api_client.get_kernel(request)
    print("current_version", current.metadata.current_version_number)
    current_source = current.blob.source
    for label in ("v1", "v7", "v12", "v16", "v17", "v18", "v21"):
        trial = ApiGetKernelRequest()
        trial.user_name = "nadhirmaamar"
        trial.kernel_slug = "dressme-high-res-clothes"
        trial.version_label = label
        try:
            found = client.kernels.kernels_api_client.get_kernel(trial)
        except Exception as error:
            print("label", label, type(error).__name__)
            continue
        same = found.blob.source == current_source
        print("label", label, "chars", len(found.blob.source), "same_as_latest", same, "reported", found.metadata.current_version_number)
        (OUT / f"{label}.ipynb").write_text(found.blob.source, encoding="utf-8")
