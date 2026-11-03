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
src = None
for root_dir in (Path('/kaggle/input'), Path('/kaggle/working'), Path('.')):
    if not root_dir.exists():
        continue
    for image in root_dir.rglob('shirt.png'):
        folder = image.parents[1]
        if image.parent.name == 'images' and (folder / 'templates' / 'smplx_canonical.obj').is_file():
            src = folder
            break
    if src is not None:
        break
if src is None:
    raise FileNotFoundError('shirt.png was not uploaded with the notebook')
print('inputs', src)
shutil.copy(src / 'templates' / 'smplx_canonical.obj', data / 'smplx_canonical.obj')
shutil.copy(src / 'templates' / 'smplx_watertight.pkl', data / 'smplx_watertight.pkl')
test = Path('/kaggle/working/test')
if test.exists():
    shutil.rmtree(test)
for name in ('images', 'back_images', 'smplx'):
    shutil.copytree(src / name, test / name)
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
