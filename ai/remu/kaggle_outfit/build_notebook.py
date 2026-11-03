"""Write the outfit pipeline notebook: GPU stack, SMPL-X fit to the photo, SiTH reconstruction.

The GPU stack and the checkpoints live in /tmp/stack and are saved as one
stack.tar in the output, so the next run (which attaches this kernel's output)
unpacks one file instead of rebuilding, and downloads stay quick. The demo
notebook in kaggle_kernel is separate and stays unchanged.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

STACK = r'''import os, shutil, subprocess, urllib.request
from pathlib import Path
os.environ['TORCH_CUDA_ARCH_LIST'] = '7.5'
os.environ['UV_PYTHON_INSTALL_DIR'] = '/tmp/stack/python'
stack = Path('/tmp/stack')
py = stack / 'venv' / 'bin' / 'python'
saved = next(Path('/kaggle/input').rglob('stack.tar'), None) if Path('/kaggle/input').exists() else None
if saved is not None and not py.exists():
    print('unpacking the saved GPU stack from', saved)
    subprocess.check_call(['tar', '-xf', str(saved), '-C', '/'])
fresh = not py.exists()
uv_dir = stack / 'uv'
if not (uv_dir.exists() and any(p.is_file() and p.name == 'uv' for p in uv_dir.rglob('uv'))):
    uv_dir.mkdir(parents=True, exist_ok=True)
    archive = uv_dir / 'uv.tar.gz'
    urllib.request.urlretrieve('https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz', archive)
    subprocess.check_call(['tar', '-xzf', str(archive), '-C', str(uv_dir)])
uv = str(next(p for p in uv_dir.rglob('uv') if p.is_file()))
pip = [uv, 'pip', 'install', '--python', str(py)]
if fresh:
    print('building the GPU stack')
    subprocess.check_call([uv, 'python', 'install', '3.12'])
    subprocess.check_call([uv, 'venv', str(stack / 'venv'), '--python', '3.12', '--python-preference', 'only-managed'])
    subprocess.check_call(pip + ['torch==2.8.0', 'torchvision==0.23.0', '--index-url', 'https://download.pytorch.org/whl/cu128'])
    subprocess.check_call(pip + ['trimesh', 'einops', 'pyyaml', 'opencv-python-headless', 'imageio', 'scikit-image', 'tqdm', 'scipy'])
    subprocess.check_call(pip + ['kaolin', '-f', 'https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.8.0_cu128.html'])
    subprocess.check_call(pip + ['--no-build-isolation', 'git+https://github.com/NVlabs/nvdiffrast.git'])
subprocess.check_call(pip + ['smplx', 'timm', 'matplotlib'])
print(subprocess.check_output([str(py), '-c', 'import torch,kaolin,nvdiffrast,smplx,timm; print(torch.__version__, torch.cuda.get_device_name(0))'], text=True))
ckpts = stack / 'checkpoints'
ckpts.mkdir(exist_ok=True)
for name in ('save_smplerx.pth', 'recon_model.pth'):
    if not (ckpts / name).exists():
        subprocess.check_call(['curl', '-L', '--fail', '-o', str(ckpts / name), f'https://files.ait.ethz.ch/projects/SiTH/{name}'])
keep = Path('/kaggle/working/stack.tar')
if fresh or saved is None:
    subprocess.check_call(['tar', '-cf', str(keep), '-C', '/', 'tmp/stack'])
else:
    shutil.copy(saved, keep)
print('stack saved', keep.stat().st_size)
'''

FIT = r'''import shutil, subprocess
from pathlib import Path
stack = Path('/tmp/stack')
py = str(stack / 'venv' / 'bin' / 'python')
work = Path('/kaggle/working')
root = Path('/tmp/ReMu')
if not root.exists():
    subprocess.check_call(['git', 'clone', '--depth', '1', 'https://github.com/eth-ait/ReMu.git', str(root)])
sith = root / 'third_party' / 'sith'
shim = """import os\nimport numpy as np\nimport torch\nimport trimesh\n\ndef load_obj(fname, load_materials=False):\n    assert os.path.exists(fname), fname\n    mesh = trimesh.load(fname, process=False, force="mesh")\n    vertices = torch.as_tensor(np.asarray(mesh.vertices), dtype=torch.float32)\n    faces = torch.as_tensor(np.asarray(mesh.faces), dtype=torch.int64)\n    return vertices, faces\n"""
for loader in (sith / 'recon' / 'models' / 'ops' / 'mesh' / 'load_obj.py', sith / 'recon' / 'datasets' / 'load_obj.py'):
    loader.write_text(shim)

def patch(path, old, new):
    text = path.read_text()
    if new and new in text:
        return
    if old not in text:
        raise SystemExit(f'patch point missing in {path.name}: {old}')
    path.write_text(text.replace(old, new))

patch(sith / 'fit.py', 'Image.Resampling.LANCZOS.LANCZOS', 'Image.Resampling.LANCZOS')
if 'verbose=0,' in (sith / 'fit.py').read_text():
    patch(sith / 'fit.py', 'verbose=0,', '')
patch(sith / 'fitting' / 'models' / 'smpler_x_model.py', "torch.load(ckpt, map_location='cpu')", "torch.load(ckpt, map_location='cpu', weights_only=False)")

inputs = Path('/kaggle/input')
src = next((p.parents[1] for p in inputs.rglob('outfit.png') if p.parent.name == 'images' and (p.parents[1] / 'templates' / 'smplx_canonical.obj').is_file()), None)
if src is None:
    raise FileNotFoundError('images/outfit.png was not attached to the notebook')
body = next(inputs.rglob('SMPLX_MALE.npz'), None)
if body is None:
    raise FileNotFoundError('SMPLX_MALE.npz was not attached to the notebook')
print('inputs', src, 'body', body)
data = sith / 'data'
(data / 'body_models' / 'smplx').mkdir(parents=True, exist_ok=True)
shutil.copy(body, data / 'body_models' / 'smplx' / 'SMPLX_MALE.npz')
for name in ('smplx_canonical.obj', 'smplx_watertight.pkl'):
    shutil.copy(src / 'templates' / name, data / name)
if not (data / 'smplx_openpose25.json').is_file():
    raise FileNotFoundError('SiTH data/smplx_openpose25.json is missing')
(sith / 'checkpoints').mkdir(exist_ok=True)
shutil.copy(stack / 'checkpoints' / 'save_smplerx.pth', sith / 'checkpoints' / 'save_smplerx.pth')

test = Path('/tmp/test')
if test.exists():
    shutil.rmtree(test)
shutil.copytree(src / 'images', test / 'images')
shutil.copytree(src / 'back_images', test / 'back_images')
print('fitting SMPL-X to the photo')
subprocess.check_call([py, 'fit.py', '-i', str(test / 'images'), '-o', str(test / 'smplx'), '--opt_orient', '--opt_betas', '--debug'], cwd=str(sith))
for keypoints in (test / 'images').glob('*.json'):
    keypoints.unlink()
fit_out = work / 'fit'
if fit_out.exists():
    shutil.rmtree(fit_out)
shutil.copytree(test / 'smplx' / 'debug', fit_out)
shutil.copy(test / 'smplx' / 'outfit_smplx.obj', work / 'outfit_smplx.obj')
print('fit', sorted(p.name for p in fit_out.iterdir()))
'''

RECON = r'''import os, shutil, subprocess
from pathlib import Path
stack = Path('/tmp/stack')
py = str(stack / 'venv' / 'bin' / 'python')
sith = Path('/tmp/ReMu/third_party/sith')
test = Path('/tmp/test')
weights = stack / 'checkpoints' / 'recon_model.pth'
env = os.environ.copy()
env['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
evaluator = sith / 'recon' / 'models' / 'evaluator.py'
source = evaluator.read_text()
needle = "vertices, faces = voxelgrids_to_trianglemeshes(voxels, iso_value=0.)"
insert = """held = self.coord
        self.coord = None
        del held, _points, front_feat, back_feat, front_nrm_img, back_nrm_img
        torch.cuda.empty_cache()
        vertices, faces = voxelgrids_to_trianglemeshes(voxels, iso_value=0.)
        window_x = torch.linspace(-1., 1., steps=self.res, device='cuda')
        window_y = torch.linspace(-1., 1., steps=self.res, device='cuda')
        window_z = torch.linspace(-1., 1., steps=self.res, device='cuda')
        self.coord = torch.stack(torch.meshgrid(window_x, window_y, window_z, indexing='ij')).permute(1, 2, 3, 0).reshape(1, -1, 3).contiguous()"""
if 'del held, _points' not in source:
    if needle not in source:
        raise SystemExit('evaluator patch point missing')
    evaluator.write_text(source.replace(needle, insert, 1))
mesh = None
for grid in (384, 256):
    staged = Path(f'/tmp/run_{grid}')
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(test, staged)
    print('reconstruct grid', grid)
    result = subprocess.run([py, 'reconstruct.py', '--test_folder', str(staged), '--config', str(sith / 'recon' / 'config.yaml'), '--resume', str(weights), '--grid_size', str(grid)], cwd=str(sith), env=env)
    found = sorted((staged / 'meshes').glob('outfit_reco.obj')) if (staged / 'meshes').exists() else []
    if result.returncode == 0 and found:
        mesh = found[0]
        break
    print('grid', grid, 'failed', result.returncode)
if mesh is None:
    raise SystemExit('no outfit mesh')
shutil.copy(mesh, '/kaggle/working/outfit_reco.obj')
print('outfit mesh', Path('/kaggle/working/outfit_reco.obj').stat().st_size)
'''


def cell(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


notebook = {
    "cells": [cell(STACK), cell(FIT), cell(RECON)],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 4,
}
(HERE / "dressme-outfit-pipeline.ipynb").write_text(json.dumps(notebook, indent=1), encoding="utf-8")

meta = {
    "id": "nadhirmaamar/dressme-outfit-pipeline",
    "title": "DressMe outfit pipeline",
    "code_file": "dressme-outfit-pipeline.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": True,
    "keywords": ["gpu"],
    "dataset_sources": ["nadhirmaamar/dressme-garment-photos", "nadhirmaamar/dressme-smplx-body"],
    "kernel_sources": [],
    "competition_sources": [],
    "model_sources": [],
    "docker_image": json.loads((HERE.parent / "kaggle_kernel" / "kernel-metadata.json").read_text(encoding="utf-8"))["docker_image"],
    "machine_shape": "NvidiaTeslaT4",
}
meta_path = HERE / "kernel-metadata.json"
if meta_path.exists():
    meta["kernel_sources"] = json.loads(meta_path.read_text(encoding="utf-8")).get("kernel_sources", [])
meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
