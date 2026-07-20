"""3D 可视化、变形矩阵、EOS 拟合"""

import json
import numpy as np
from scipy.optimize import curve_fit
from pymatgen.core import Structure


def visualize_structure(poscar_path, save_path):
    from pymatgen.core import Structure
    import json

    structure = Structure.from_file(poscar_path)
    cif_str = structure.to(fmt='cif')

    # Default radii
    atom_radii_real = {
        'H': 0.46, 'He': 1.22, 'Li': 1.57, 'Be': 1.12, 'B': 0.81, 'C': 0.77, 'N': 0.74, 'O': 0.74, 'F': 0.72, 'Ne': 1.60,
        'Na': 1.91, 'Mg': 1.60, 'Al': 1.43, 'Si': 1.18, 'P': 1.10, 'S': 1.04, 'Cl': 0.99, 'Ar': 1.92, 'K': 2.35, 'Ca': 1.97,
        'Sc': 1.64, 'Ti': 1.47, 'V': 1.35, 'Cr': 1.29, 'Mn': 1.37, 'Fe': 1.26, 'Co': 1.25, 'Ni': 1.25, 'Cu': 1.28, 'Zn': 1.37,
        'Ga': 1.53, 'Ge': 1.22, 'As': 1.21, 'Se': 1.04, 'Br': 1.14, 'Kr': 1.98, 'Rb': 2.50, 'Sr': 2.15, 'Y': 1.82, 'Zr': 1.60,
        'Nb': 1.47, 'Mo': 1.40, 'Tc': 1.35, 'Ru': 1.34, 'Rh': 1.34, 'Pd': 1.37, 'Ag': 1.44, 'Cd': 1.52, 'In': 1.67, 'Sn': 1.58,
        'Sb': 1.41, 'Te': 1.37, 'I': 1.33, 'Xe': 2.18, 'Cs': 2.71, 'Ba': 2.24, 'La': 1.88, 'Ce': 1.82, 'Pr': 1.82, 'Nd': 1.82,
        'Pm': 1.81, 'Sm': 1.81, 'Eu': 2.06, 'Gd': 1.79, 'Tb': 1.77, 'Dy': 1.77, 'Ho': 1.76, 'Er': 1.75, 'Tm': 1.00, 'Yb': 1.94,
        'Lu': 1.72, 'Hf': 1.59, 'Ta': 1.47, 'W': 1.41, 'Re': 1.37, 'Os': 1.35, 'Ir': 1.36, 'Pt': 1.39, 'Au': 1.44, 'Hg': 1.55,
        'Tl': 1.71, 'Pb': 1.75, 'Bi': 1.82, 'Po': 1.77, 'At': 0.62, 'Rn': 0.80, 'Fr': 1.00, 'Ra': 2.35, 'Ac': 2.03, 'Th': 1.80,
        'Pa': 1.63, 'U': 1.56, 'Np': 1.56, 'Pu': 1.64, 'Am': 1.73, 'Cm': 0.80, 'Bk': 0.80, 'Cf': 0.80, 'Es': 0.80, 'Fm': 0.80,
        'Md': 0.80, 'No': 0.80, 'Lr': 0.80, 'Rf': 0.80, 'Db': 0.80, 'Sg': 0.80, 'Bh': 0.80, 'Hs': 0.80, 'Mt': 0.80, 'Ds': 0.80,
        'Rg': 0.80, 'Cn': 0.80, 'Nh': 0.80, 'Fl': 0.80, 'Mc': 0.80, 'Lv': 0.80, 'Ts': 0.80, 'Og': 0.80,
    }
    # Scale radii for better visualization
    atom_radii_scaled = {elem: radius * 0.3 for elem, radius in atom_radii_real.items()}
    atom_radii_js = json.dumps(atom_radii_scaled)

    # Create HTML content
    html = f'''
    <html>
    <head>
    <script src='https://3Dmol.org/build/3Dmol.js'></script>
    <style>
        body {{ 
            margin: 0; 
            overflow: hidden; 
        }}

        #viewer {{
            width: 100vw;
            height: 100vh;
            position: relative;
        }}

        .overlay {{
            position: absolute;
            background: rgba(255, 255, 255, 0.85);
            border-radius: 6px;
            padding: 8px 12px;
            font-family: Arial, sans-serif;
            font-size: 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }}

        #title {{ 
            top: 10px; 
            left: 10px;
            font-weight: bold;
            font-size: 20px;
        }}

        #legend {{ 
            top: 10px; 
            right: 10px; 
        }}

        #instructions {{ 
            bottom: 10px; 
            right: 10px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin: 10px 0;
        }}

        .color-box {{
            width: 20px;
            height: 20px;
            margin-right: 6px;
            border: 1px solid #444;
            border-radius: 10px;
        }}

        #controls {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            display: flex;
            gap: 8px;
        }}

        .control-btn {{
            padding: 6px 12px;
            font-size: 14px;
            border-radius: 4px;
            border: 1px solid #444;
            background: white;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}

        .control-btn:hover {{
            background: #f0f0f0;
        }}
    </style>
    </head>

    <body>
    <div id='viewer'></div>

    <div id="controls">
        <button class="control-btn" onclick="rotateX()">Rotate X</button>
        <button class="control-btn" onclick="rotateY()">Rotate Y</button>
        <button class="control-btn" onclick="rotateZ()">Rotate Z</button>
        <button class="control-btn" onclick="resetView()">Reset</button>
        <button class="control-btn" onclick="save()">Save</button>
    </div>

    <div id='title' class='overlay'>
        Masgent Structure Viewer (Powered by 3Dmol.js)
    </div>

    <div id='legend' class='overlay'>
        <strong>Elements</strong>
        <div id='legend-items'></div>
    </div>

    <div id='instructions' class='overlay'>
        <strong>Instructions:</strong><br>
        * Drag to rotate<br>
        * Scroll to zoom
    </div>

    <script>
        let viewer = $3Dmol.createViewer('viewer', {{ backgroundColor: 'white' }});
        viewer.setProjection('orthographic');
        viewer.addModel(`{cif_str}`, 'cif');

        const atomRadii = {atom_radii_js};

        // Apply custom radii
        Object.entries(atomRadii).forEach(([elem, radius]) => {{
            viewer.setStyle(
                {{ elem: elem }},
                {{ sphere: {{ scale: radius, colorscheme: 'Jmol' }} }}
            );
        }});

        viewer.addUnitCell();
        viewer.zoomTo();
        viewer.render();

        const baseView = viewer.getView();

        // View control functions
        function rotateX() {{
            viewer.rotate(15, 'x');
            viewer.render();
        }}

        function rotateY() {{
            viewer.rotate(15, 'y');
            viewer.render();
        }}

        function rotateZ() {{
            viewer.rotate(15, 'z');
            viewer.render();
        }}

        function resetView() {{
            viewer.setView(baseView);
            viewer.zoomTo();
            viewer.render();
        }}

        // Save function
        function save() {{
            const canvas = viewer.getCanvas();

            // Save original size
            const originalWidth = canvas.width;
            const originalHeight = canvas.height;

            // Increase resolution (2x for publication quality)
            const scale = window.devicePixelRatio || 2;
            canvas.width = originalWidth * scale;
            canvas.height = originalHeight * scale;

            viewer.render();

            // Export image
            const dataURL = canvas.toDataURL("image/png");
            const link = document.createElement('a');
            link.href = dataURL;
            link.download = 'structure.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Restore original size
            canvas.width = originalWidth;
            canvas.height = originalHeight;
            viewer.render();
        }}

        // Build legend from Jmol colors of displayed elements
        const atoms = viewer.getModel().selectedAtoms();
        const elements = [...new Set(atoms.map(a => a.elem))].sort();

        const legend = document.getElementById('legend-items');
        elements.forEach(el => {{
            const color = $3Dmol.elementColors.Jmol[el] || 0xAAAAAA;
            const hex = '#' + color.toString(16).padStart(6, '0');

            const item = document.createElement('div');
            item.className = 'legend-item';

            const box = document.createElement('div');
            box.className = 'color-box';
            box.style.background = hex;

            const label = document.createElement('span');
            label.textContent = el;

            item.appendChild(box);
            item.appendChild(label);
            legend.appendChild(item);
        }});
    </script>
    </body>
    </html>
    '''

    # Save HTML file
    with open(save_path, 'w') as f:
        f.write(html)


def create_deformation_matrices():
    """生成弹性常数计算用的 13 个应变矩阵"""
    xx = [-0.010, 0.010]
    yy = [-0.010, 0.010]
    zz = [-0.010, 0.010]
    xy = [-0.005, 0.005]
    yz = [-0.005, 0.005]
    xz = [-0.005, 0.005]
    D_000 = {f'00_strain_0.000': [[0,0,0],[0,0,0],[0,0,0]]}
    D_xx0 = {f'01_strain_xx_{xx[0]:.3f}': [[xx[0],0,0],[0,0,0],[0,0,0]]}
    D_yy0 = {f'03_strain_yy_{yy[0]:.3f}': [[0,0,0],[0,yy[0],0],[0,0,0]]}
    D_zz0 = {f'05_strain_zz_{zz[0]:.3f}': [[0,0,0],[0,0,0],[0,0,zz[0]]]}
    D_xy0 = {f'07_strain_xy_{xy[0]:.3f}': [[0,xy[0],0],[xy[0],0,0],[0,0,0]]}
    D_yz0 = {f'09_strain_yz_{yz[0]:.3f}': [[0,0,0],[0,0,yz[0]],[0,yz[0],0]]}
    D_xz0 = {f'11_strain_xz_{xz[0]:.3f}': [[0,0,xz[0]],[0,0,0],[xz[0],0,0]]}
    D_xx1 = {f'02_strain_xx_{xx[1]:.3f}': [[xx[1],0,0],[0,0,0],[0,0,0]]}
    D_yy1 = {f'04_strain_yy_{yy[1]:.3f}': [[0,0,0],[0,yy[1],0],[0,0,0]]}
    D_zz1 = {f'06_strain_zz_{zz[1]:.3f}': [[0,0,0],[0,0,0],[0,0,zz[1]]]}
    D_xy1 = {f'08_strain_xy_{xy[1]:.3f}': [[0,xy[1],0],[xy[1],0,0],[0,0,0]]}
    D_yz1 = {f'10_strain_yz_{yz[1]:.3f}': [[0,0,0],[0,0,yz[1]],[0,yz[1],0]]}
    D_xz1 = {f'12_strain_xz_{xz[1]:.3f}': [[0,0,xz[1]],[0,0,0],[xz[1],0,0]]}
    return [D_000, D_xx0, D_yy0, D_zz0, D_xy0, D_yz0, D_xz0, D_xx1, D_yy1, D_zz1, D_xy1, D_yz1, D_xz1]


def _eos_func(volume, a, b, c, d):
    return a + b * volume**(-2/3) + c * volume**(-4/3) + d * volume**(-2)


def fit_eos(volumes, energies):
    """拟合 Birch-Murnaghan 状态方程"""
    volumes_fit = np.linspace(min(volumes) * 0.99, max(volumes) * 1.01, 100)
    popt, _ = curve_fit(_eos_func, volumes, energies)
    energies_fit = _eos_func(volumes_fit, *popt)
    return volumes_fit, energies_fit