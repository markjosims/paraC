import flask
from flask import Flask, render_template, request
from src.forms import parse_inflected_verb, inflect_verb_with_features, FV_CLASSES
from src.lexicon import get_all_verb_data
from src.constants import VERB_FEATURE_VALUES

# --- Flask Application ---
app = Flask(__name__)

TEMPLATE_DEFAULTS = {
    "feature_options": VERB_FEATURE_VALUES,
    "fv_classes": FV_CLASSES,
    "verb_lexicon": get_all_verb_data(),
}

@app.route('/')
def index():
    """Renders the main page."""
    return render_template("index.html", **TEMPLATE_DEFAULTS)

@app.route('/parse', methods=['POST'])
def handle_parse():
    """Handles the parsing form submission."""
    inflected_form = request.form.get('inflected_form', '')
    fv_class = request.form.get('fv_class')
    if not inflected_form:
        result = {"error": "Please enter a verb form."}
    else:
        result = parse_inflected_verb(inflected_form, fv_class)
    result['form']=inflected_form
    return render_template(
        "index.html",
        parse_result=result,
        **TEMPLATE_DEFAULTS,
    )

@app.route('/inflect', methods=['POST'])
def handle_inflect():
    """Handles the inflection form submission."""
    verb_row = request.form.get('verb_root', '')
    verb_root, fv, _ = verb_row.split()
    features = {
        'tam': request.form.get('tam'),
        'deixis': request.form.get('deixis'),
        'class': request.form.get('class')
    }
    
    if not verb_root:
        result = "Please enter a verb root."
    else:
        result = inflect_verb_with_features(verb_root, fv, features)

    return render_template(
        "index.html",
        inflect_result=result,
        **TEMPLATE_DEFAULTS,
    )

@app.route('/lexicon')
def lexicon_page():
    """
    Handles the lexicon page.
    Fetches all verb data and displays it in a table.
    """
    return render_template('lexicon.html', **TEMPLATE_DEFAULTS)

if __name__ == '__main__':
    app.run(debug=True)