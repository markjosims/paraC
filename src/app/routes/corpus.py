import math

from flask import Blueprint, render_template, request, jsonify

from src.search import search_corpus, search_parse_csv
from src.app.utils import get_weight_color

bp = Blueprint('corpus', __name__)


@bp.route('/')
def index():
    return render_template('corpus.html')


@bp.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query', '').strip()
    query_type = data.get('query_type', 'tira')
    whole_word = data.get('whole_word', False)

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        results = search_corpus(query, query_type=query_type, whole_word=whole_word)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


PARSE_COLUMNS = ['original_str', 'updated_str', 'gloss', 'root', 'weight', 'sentence', 'translation']


@bp.route('/search-parses', methods=['POST'])
def search_parses():
    data = request.get_json()
    root = data.get('root', '').strip() or None
    feature_str = data.get('feature', '').strip()
    max_cost = float(data.get('max_cost', 10))

    features_list = [f.strip() for f in feature_str.split(',')] if feature_str else []

    try:
        results = search_parse_csv(root=root, features=features_list, max_cost=max_cost)
        for result in results:
            weight = result.get('weight', 0)
            if weight is None or (isinstance(weight, float) and math.isnan(weight)):
                weight = 0
            updated_str = result.get('updated_str', None)
            if not updated_str:
                result['updated_str'] = result['word']
            result['color'] = get_weight_color(float(weight), max_weight=10)
        return jsonify({'results': results, 'columns': PARSE_COLUMNS})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
