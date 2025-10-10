import flask
from flask import Flask, jsonify, render_template, request
from src.form_builders.verb_forms import (
    parse_inflected_verb,
    inflect_verb_with_features,
    get_inflected_paradigm_for_verb,
    FV_CLASSES
)
from src.lexicon import get_all_verb_data
from src.constants import VERB_FEATURE_VALUES
from src.sentences import get_elan_analyses
import pynini
from unicodedata import normalize
from sqlalchemy.orm import joinedload, selectinload
from src.database.database import SessionLocal
from src.database.models import Sentence, SentenceWord, Wordform
import math

app = Flask(__name__)

TEMPLATE_DEFAULTS = {
    "feature_options": VERB_FEATURE_VALUES,
    "fv_classes": FV_CLASSES,
    "verb_lexicon": get_all_verb_data(),
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """Renders the main page."""
    mode = request.args.get('mode', 'default')
    context = {'mode': mode, 'inflect_input': {}, 'parse_input': ''}

    if request.method == 'POST':
        if 'submit_parse' in request.form and mode == 'test':
            result = handle_test_parse(request.form)
        elif 'submit_parse' in request.form:
            result = handle_parse(request.form)
        elif 'submit_inflect' in request.form and mode == 'test':
            result = handle_test_inflect(request.form)
        elif 'submit_inflect' in request.form:
            result = handle_inflect(request.form)
        context.update(result)

    return render_template("index.html", **TEMPLATE_DEFAULTS, **context)

def handle_parse(form):
    """Handles the parsing form submission."""
    normalize_parse_input = lambda s: normalize("NFKD", s).replace('-', '')
    parse_input = form.get('parse_input', '')
    parse_input = normalize_parse_input(parse_input)

    fv_class = form.get('fv_class')
    if not parse_input:
        result = {"error": "Please enter a verb form."}
    else:
        result = parse_inflected_verb(parse_input, fv_class)
    result['form']=parse_input

    return {'parse_result': result}

def handle_test_parse(form):
    parse_input = form.get('parse_input', '').strip()
    verb_row = form.get('verb_root', '')
    verb_root, fv, gloss = verb_row.split()

    expected = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class'),
        'root': verb_root,
        'gloss': gloss,
    }
    actual = parse_inflected_verb(parse_input, fv)
    actual_filtered = {key: actual.get(key) for key in expected.keys()}
    
    if actual_filtered == expected:
        status = "Success"
    else:
        status = "Failure"

    return {
        "test_parse_result": {
            "status": status,
            "expected": expected,
            "actual": actual,
        },
        "parse_input": parse_input,
    }

def handle_inflect(form):
    """Handles the inflection form submission."""
    verb_row = form.get('verb_root', '')
    verb_root, fv, _ = verb_row.split()
    features = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class')
    }
    
    if not verb_root:
        result = "Please enter a verb root."
    else:
        try:
            result = inflect_verb_with_features(verb_root, fv, features)
        except:
            result = "Invalid feature combination."

    return {
        'inflect_result': result,
        'inflect_input': {
            'verb_root': verb_row,
            **features,
        }
    }

def handle_test_inflect(form):
    verb_row = form.get('verb_root', '')
    verb_root, fv, _ = verb_row.split()
    features = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class')
    }
    normalize_inflect_input = lambda s: normalize("NFKD", s)
    expected = form.get('expected_inflected_form', '').strip()
    expected = normalize_inflect_input(expected)

    actual = inflect_verb_with_features(verb_root, fv, features)

    if actual == expected:
        status = "Success"
    else:
        status = "Failure"
    
    return {
        'test_inflect_result': {
            "status": status,
            "expected": expected,
            "actual": actual,
        },
        'inflect_input': {
            'verb_root': verb_row,
            **features,
        },
        'expected_inflected_form': expected,
    }

@app.route('/lexicon')
def lexicon_page():
    """
    Handles the lexicon page.
    Fetches all verb data and displays it in a table.
    """
    return render_template('lexicon.html', **TEMPLATE_DEFAULTS)

@app.route('/paradigms', methods=['GET', 'POST'])
def paradigms_page():
    context = {'paradigm': None, 'inflect_input': None}
    if request.method == 'POST':
        verb_row = request.form.get('verb_root', '')
        verb_root, fv, _ = verb_row.split()
        context['paradigm']=get_inflected_paradigm_for_verb(verb_root, fv)
        context['inflect_input']=verb_row
    return render_template('paradigms.html', **TEMPLATE_DEFAULTS, **context)

@app.route('/sentences')
def sentences_page():
    """
    Displays the list of all sentences from the database with pagination.
    """
    # Get the page number from the URL query, defaulting to 1
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Sentences to display per page

    db = SessionLocal()
    
    # Get the total number of sentences to calculate total pages
    total_sentences = db.query(Sentence).count()
    
    # Fetch only the sentences for the current page
    sentences_data = db.query(Sentence).order_by(Sentence.id).limit(per_page).offset((page - 1) * per_page).all()
    
    db.close()
    
    # Calculate the total number of pages
    total_pages = math.ceil(total_sentences / per_page)
    
    return render_template('sentences.html', 
                           sentences=sentences_data,
                           page=page,
                           total_pages=total_pages)

@app.route('/analyze/<int:sentence_id>')
def analyze_page(sentence_id):
    """
    Displays a single sentence for analysis.
    """
    db = SessionLocal()
    sentence = db.query(Sentence).options(
        selectinload(Sentence.words).joinedload(SentenceWord.wordform),
        selectinload(Sentence.words).joinedload(SentenceWord.chosen_parse),
        selectinload(Sentence.words).joinedload(SentenceWord.wordform).joinedload(Wordform.parses)
    ).filter(Sentence.id == sentence_id).first()
    db.close()
    print(sentence.words[0].wordform.parses)

    if not sentence:
        return "Sentence not found", 404
    
    words_in_order = sorted(sentence.words, key=lambda w: w.position)
    print(words_in_order)

    return render_template('analyze.html', sentence=sentence, words=words_in_order)

@app.route('/api/sentence_words/<int:sentence_word_id>/set_parse', methods=['POST'])
def set_chosen_parse(sentence_word_id):
    data = request.get_json()
    parse_id = data.get('parse_id')

    if not parse_id:
        return jsonify({"error": "parse_id is required"}), 400

    db = SessionLocal()
    
    # Find the specific word in the sentence to update
    sentence_word = db.query(SentenceWord).filter(SentenceWord.id == sentence_word_id).first()

    if not sentence_word:
        db.close()
        return jsonify({"error": "SentenceWord not found"}), 404

    # Update the chosen parse ID
    sentence_word.chosen_parse_id = parse_id
    
    parent_sentence = db.query(Sentence).options(
        selectinload(Sentence.words).joinedload(SentenceWord.wordform),
        selectinload(Sentence.words).joinedload(SentenceWord.chosen_parse),
        selectinload(Sentence.words).joinedload(SentenceWord.wordform).joinedload(Wordform.parses)
    ).filter(Sentence.id == sentence_word.sentence_id).first()

    words_in_order = sorted(parent_sentence.words, key=lambda w: w.position)

    new_sentence_parts = []
    for word in words_in_order:
        if word.chosen_parse and word.chosen_parse.updated_form:
            new_sentence_parts.append(word.chosen_parse.updated_form)
        else:
            new_sentence_parts.append(word.wordform.text)
    
    parent_sentence.updated_sentence = " ".join(new_sentence_parts)

    db.commit()
    
    response_data = {"message": "Parse chosen successfully", "updated_sentence": parent_sentence.updated_sentence}
    
    db.close()

    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(debug=True)