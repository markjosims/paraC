import os
import yaml
from flask import Blueprint, render_template, request, jsonify

bp = Blueprint('config', __name__)

CONFIG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config'))


def _safe_path(relative_path):
    """Resolve a relative path under CONFIG_ROOT, preventing directory traversal."""
    full = os.path.normpath(os.path.join(CONFIG_ROOT, relative_path))
    if not full.startswith(CONFIG_ROOT):
        return None
    return full


def _build_tree(root_dir):
    """Build a nested dict representing the directory tree."""
    tree = []
    try:
        entries = sorted(os.listdir(root_dir))
    except OSError:
        return tree
    for entry in entries:
        full = os.path.join(root_dir, entry)
        rel = os.path.relpath(full, CONFIG_ROOT)
        if os.path.isdir(full):
            tree.append({
                'name': entry,
                'path': rel,
                'type': 'directory',
                'children': _build_tree(full),
            })
        elif entry.endswith(('.yaml', '.yml')):
            tree.append({
                'name': entry,
                'path': rel,
                'type': 'file',
            })
    return tree


def _collect_symbols_from_inventory(data):
    """Recursively extract repr -> items/phones/flags from inventory data as a tree."""
    if not isinstance(data, dict):
        return []
    trees = []
    for key, val in data.items():
        if key in ('repr', 'items', 'phones', 'flags'):
            continue
        if not isinstance(val, dict) or not val.get('repr'):
            continue
        node = {'repr': val['repr']}
        items = val.get('items') or val.get('phones') or val.get('flags')
        if items:
            node['items'] = items
        children = _collect_symbols_from_inventory(val)
        if children:
            node['children'] = children
        trees.append(node)
    return trees


def _collect_references():
    """Scan config/ for available $-references, grouped by directory."""
    refs = {}
    for dirpath, _dirnames, filenames in os.walk(CONFIG_ROOT):
        category = os.path.relpath(dirpath, CONFIG_ROOT)
        if category == '.':
            continue
        items = []
        for fname in sorted(filenames):
            if not fname.endswith(('.yaml', '.yml')):
                continue
            ref_name = os.path.splitext(fname)[0]
            full_path = os.path.join(dirpath, fname)
            info = {'name': ref_name, 'ref': f'${ref_name}'}
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    doc = yaml.safe_load(f)
                if isinstance(doc, dict):
                    info['kind'] = doc.get('kind', '')
                    # For rules files, extract individual rule names and details
                    if doc.get('kind') == 'Rules' and isinstance(doc.get('rules'), dict):
                        info['rule_names'] = list(doc['rules'].keys())
                        rule_details = {}
                        for rname, rdef in doc['rules'].items():
                            if isinstance(rdef, dict):
                                detail = {}
                                if rdef.get('description'):
                                    detail['description'] = rdef['description'].strip()
                                if rdef.get('input_pattern'):
                                    detail['input_pattern'] = rdef['input_pattern']
                                if rdef.get('output_pattern') is not None:
                                    detail['output_pattern'] = rdef['output_pattern']
                                if rdef.get('left_context'):
                                    detail['left_context'] = rdef['left_context']
                                if rdef.get('right_context'):
                                    detail['right_context'] = rdef['right_context']
                                if rdef.get('rule_sequence'):
                                    detail['rule_sequence'] = rdef['rule_sequence']
                                if rdef.get('string_map'):
                                    detail['string_map'] = True
                                rule_details[rname] = detail
                        info['rule_details'] = rule_details
                    # For inventory files, extract symbols
                    if doc.get('kind') == 'Inventory' and isinstance(doc.get('data'), dict):
                        info['symbols'] = _collect_symbols_from_inventory(doc['data'])
                    # For markers, extract feature and marker values
                    if doc.get('kind') == 'FeatureMarkers':
                        info['feature'] = doc.get('feature', '')
                        if isinstance(doc.get('markers'), dict):
                            info['values'] = list(doc['markers'].keys())
                    if doc.get('kind') == 'ContingentFeatureMarkers':
                        info['features'] = doc.get('features', [])
                    # For patterns, extract repr values and pattern strings
                    if doc.get('kind') == 'Patterns' and isinstance(doc.get('patterns'), list):
                        reprs = []
                        for p in doc['patterns']:
                            if isinstance(p, dict):
                                for pname, pdef in p.items():
                                    if isinstance(pdef, dict) and 'repr' in pdef:
                                        pat = pdef.get('pattern', '')
                                        if isinstance(pat, list):
                                            pat = ', '.join(str(x) for x in pat)
                                        reprs.append({
                                            'name': pname,
                                            'repr': pdef['repr'],
                                            'pattern': str(pat),
                                        })
                        info['patterns'] = reprs
                    # For features, extract feature names and values
                    if doc.get('kind') == 'FeatureDefinitions':
                        if isinstance(doc.get('features'), dict):
                            info['features'] = {
                                k: v for k, v in doc['features'].items()
                            }
                    if doc.get('kind') == 'FeatureCombinations':
                        info['combo_features'] = doc.get('features', [])
            except Exception:
                pass
            items.append(info)
        if items:
            refs[category] = items
    return refs


@bp.route('/')
def editor():
    return render_template('config.html')


@bp.route('/api/tree')
def get_tree():
    tree = _build_tree(CONFIG_ROOT)
    return jsonify(tree)


@bp.route('/api/file', methods=['GET'])
def get_file():
    rel_path = request.args.get('path', '')
    if not rel_path:
        return jsonify({'error': 'No path specified'}), 400
    full_path = _safe_path(rel_path)
    if full_path is None or not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        parsed = yaml.safe_load(raw)
        return jsonify({'raw': raw, 'parsed': parsed, 'path': rel_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/file', methods=['PUT'])
def save_file():
    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({'error': 'No path specified'}), 400
    full_path = _safe_path(data['path'])
    if full_path is None:
        return jsonify({'error': 'Invalid path'}), 400
    content = data.get('content', '')
    # Validate YAML
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        return jsonify({'error': f'Invalid YAML: {e}'}), 400
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'ok': True, 'path': data['path']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/file', methods=['POST'])
def create_file():
    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({'error': 'No path specified'}), 400
    full_path = _safe_path(data['path'])
    if full_path is None:
        return jsonify({'error': 'Invalid path'}), 400
    if os.path.exists(full_path):
        return jsonify({'error': 'File already exists'}), 409
    content = data.get('content', '')
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'ok': True, 'path': data['path']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/file', methods=['DELETE'])
def delete_file():
    rel_path = request.args.get('path', '')
    if not rel_path:
        return jsonify({'error': 'No path specified'}), 400
    full_path = _safe_path(rel_path)
    if full_path is None or not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404
    try:
        os.remove(full_path)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/file/rename', methods=['POST'])
def rename_file():
    data = request.get_json()
    if not data or 'old_path' not in data or 'new_name' not in data:
        return jsonify({'error': 'old_path and new_name required'}), 400
    old_full = _safe_path(data['old_path'])
    if old_full is None or not os.path.isfile(old_full):
        return jsonify({'error': 'File not found'}), 404
    new_name = data['new_name'].strip()
    if not new_name:
        return jsonify({'error': 'New name cannot be empty'}), 400
    if not new_name.endswith(('.yaml', '.yml')):
        new_name += '.yaml'
    new_full = os.path.join(os.path.dirname(old_full), new_name)
    new_full = os.path.normpath(new_full)
    if not new_full.startswith(CONFIG_ROOT):
        return jsonify({'error': 'Invalid path'}), 400
    if os.path.exists(new_full):
        return jsonify({'error': 'A file with that name already exists'}), 409
    try:
        os.rename(old_full, new_full)
        new_rel = os.path.relpath(new_full, CONFIG_ROOT)
        return jsonify({'ok': True, 'new_path': new_rel})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/references')
def get_references():
    refs = _collect_references()
    return jsonify(refs)
