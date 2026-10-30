"""Kaggle GPU script for the finer shirt, shorts, and vest.

Private notebook: nadhirmaamar/dressme-high-res-clothes
It runs on a Tesla T4. Kaggle's own Python is 3.13 and has no Conda, so this
creates a Python 3.12 environment first. SiTH's OBJ loader does not install
there, so the mesh loader is replaced with trimesh before reconstruction.
"""

# Cell 1 — install the GPU stack
SETUP = r"""
import os, subprocess, urllib.request
from pathlib import Path
import torch
print('notebook torch', torch.__version__, 'gpu', torch.cuda.get_device_name(0))
os.environ['TORCH_CUDA_ARCH_LIST'] = '7.5'
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
saved = None
if Path('/kaggle/input').exists():
    for marker in Path('/kaggle/input').rglob('remu_python.txt'):
        if (marker.parent / 'venv' / 'bin' / 'python').is_file():
            saved = marker.parent
            break
if saved is not None:
    print('reusing saved environment from', saved)
    subprocess.check_call(['cp', '-a', str(saved / 'venv'), '/kaggle/working/venv'])
    if (saved / 'uv').exists():
        subprocess.check_call(['cp', '-a', str(saved / 'uv'), '/kaggle/working/uv'])
    Path('/kaggle/working/remu_python.txt').write_text('/kaggle/working/venv/bin/python')
    py = Path('/kaggle/working/venv/bin/python')
else:
    uv_dir = Path('/kaggle/working/uv')
    uv_dir.mkdir(exist_ok=True)
    archive = uv_dir / 'uv.tar.gz'
    urllib.request.urlretrieve('https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz', archive)
    subprocess.check_call(['tar', '-xzf', str(archive), '-C', str(uv_dir)])
    uv = str(next(uv_dir.rglob('uv')))
    subprocess.check_call([uv, 'python', 'install', '3.12'])
    venv = Path('/kaggle/working/venv')
    subprocess.check_call([uv, 'venv', str(venv), '--python', '3.12'])
    py = venv / 'bin' / 'python'
    Path('/kaggle/working/remu_python.txt').write_text(str(py))
    pip = [uv, 'pip', 'install', '--python', str(py)]
    subprocess.check_call(pip + ['torch==2.8.0', 'torchvision==0.23.0', '--index-url', 'https://download.pytorch.org/whl/cu128'])
    subprocess.check_call(pip + ['trimesh', 'einops', 'pyyaml', 'opencv-python-headless', 'imageio', 'scikit-image', 'tqdm', 'scipy'])
    subprocess.check_call(pip + ['kaolin', '-f', 'https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.8.0_cu128.html'])
    subprocess.check_call(pip + ['--no-build-isolation', 'git+https://github.com/NVlabs/nvdiffrast.git'])
print(subprocess.check_output([str(py), '-c', 'import torch,kaolin,nvdiffrast; print(torch.__version__, torch.cuda.get_device_name(0))'], text=True))
print('Keep this run: Save Version with Always save output, then New Dataset from that output. Add the dataset next time and this cell copies it instead of downloading.')
"""

# Cell 2 — reconstruct at the fine grid, then 384, then 256 if the GPU runs out of memory
RECON = r"""
import os, shutil, subprocess
from pathlib import Path
root = Path('/kaggle/working/ReMu')
py = Path('/kaggle/working/remu_python.txt').read_text().strip()
if not root.exists():
    cached = None
    if Path('/kaggle/input').exists():
        cached = next((item for item in Path('/kaggle/input').rglob('reconstruct.py') if item.parent.name == 'sith'), None)
    if cached is not None:
        repo = cached
        while repo.name != 'ReMu' and repo.parent != repo:
            repo = repo.parent
        print('reusing saved ReMu from', repo)
        shutil.copytree(repo, root)
    else:
        subprocess.check_call(['git', 'clone', '--depth', '1', 'https://github.com/eth-ait/ReMu.git', str(root)])
sith = root / 'third_party' / 'sith'
shim = '''import os\nimport numpy as np\nimport torch\nimport trimesh\n\ndef load_obj(fname, load_materials=False):\n    assert os.path.exists(fname), fname\n    mesh = trimesh.load(fname, process=False, force="mesh")\n    vertices = torch.as_tensor(np.asarray(mesh.vertices), dtype=torch.float32)\n    faces = torch.as_tensor(np.asarray(mesh.faces), dtype=torch.int64)\n    return vertices, faces\n'''
for loader in (
    sith / 'recon' / 'models' / 'ops' / 'mesh' / 'load_obj.py',
    sith / 'recon' / 'datasets' / 'load_obj.py',
):
    loader.write_text(shim)
data = sith / 'data'
data.mkdir(parents=True, exist_ok=True)
candidates = [
    Path('/kaggle/working/inputs'),
    Path('inputs'),
    Path('/kaggle/input/dressme-remu-inputs'),
]
src = next((item for item in candidates if (item / 'templates' / 'smplx_canonical.obj').is_file()), None)
if src is None:
    hits = []
    for root_dir in (Path('/kaggle/working'), Path('/kaggle/input')):
        if root_dir.exists():
            hits.extend(root_dir.rglob('smplx_canonical.obj'))
    if not hits:
        raise FileNotFoundError('smplx_canonical.obj was not uploaded with the notebook')
    src = hits[0].parent.parent
print('inputs', src)
shutil.copy(src / 'templates' / 'smplx_canonical.obj', data / 'smplx_canonical.obj')
shutil.copy(src / 'templates' / 'smplx_watertight.pkl', data / 'smplx_watertight.pkl')
test = Path('/kaggle/working/test')
if test.exists():
    shutil.rmtree(test)
for name in ('images', 'back_images', 'smplx'):
    shutil.copytree(src / name, test / name)
# This run builds the shoe layer only. Shirt, shorts, and vest stay in the dataset.
keep = 'Shoes'
for folder in ('images', 'back_images', 'smplx'):
    for item in (test / folder).iterdir():
        if keep not in item.name:
            item.unlink()
print('layers', sorted(p.name for p in (test / 'images').iterdir()))
ckpt = root / 'checkpoints' / 'sith'
ckpt.mkdir(parents=True, exist_ok=True)
weights = ckpt / 'recon_model.pth'
if not weights.exists():
    subprocess.check_call(['curl', '-L', '--fail', '-o', str(weights), 'https://files.ait.ethz.ch/projects/SiTH/recon_model.pth'])
env = os.environ.copy()
env['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
evaluator = sith / 'recon' / 'models' / 'evaluator.py'
source = evaluator.read_text()
needle = "vertices, faces = voxelgrids_to_trianglemeshes(voxels, iso_value=0.)"
insert = '''held = self.coord
        self.coord = None
        del held, _points, front_feat, back_feat, front_nrm_img, back_nrm_img
        torch.cuda.empty_cache()
        vertices, faces = voxelgrids_to_trianglemeshes(voxels, iso_value=0.)
        window_x = torch.linspace(-1., 1., steps=self.res, device='cuda')
        window_y = torch.linspace(-1., 1., steps=self.res, device='cuda')
        window_z = torch.linspace(-1., 1., steps=self.res, device='cuda')
        self.coord = torch.stack(torch.meshgrid(window_x, window_y, window_z, indexing='ij')).permute(1, 2, 3, 0).reshape(1, -1, 3).contiguous()'''
if needle not in source:
    raise SystemExit('evaluator patch point missing')
evaluator.write_text(source.replace(needle, insert, 1))
last = 1
for grid in (384, 256):
    out = Path(f'/kaggle/working/meshes_{grid}')
    if out.exists():
        shutil.rmtree(out)
    staged = Path(f'/kaggle/working/run_{grid}')
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(test, staged)
    print('reconstruct grid', grid)
    result = subprocess.run([
        py, 'reconstruct.py',
        '--test_folder', str(staged),
        '--config', str(sith / 'recon' / 'config.yaml'),
        '--resume', str(weights),
        '--grid_size', str(grid),
    ], cwd=str(sith), env=env)
    last = result.returncode
    meshes = staged / 'meshes'
    if result.returncode == 0 and meshes.exists() and any(meshes.glob('*.obj')):
        shutil.copytree(meshes, out)
        print('saved', out)
        break
    print('grid', grid, 'failed', result.returncode)
if last != 0:
    raise SystemExit(last)
"""
