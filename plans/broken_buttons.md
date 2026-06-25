# Broken buttons

## Add item buttons

- RuleSequence -> Add Rule button doesn't create a new widget
- FeatureValues -> Add value button doesn't create a new widget

## Name/ref instability

- Changing a pattern or inventory ref causes the popover to be closed on re-render or for a DIFFERENT item to be focused on re-render!
- Not sure what triggers which direction: sometimes it depends on whether the string is valid before/after change, sometimes it seems to depend on where I am in the widget tree.

## Overeager expander collapsing

- MorphemeSet and ContingentMarker feature selection menu automatically closes on clicking the first feature.
  Not ideal.
  Remove auto expand/collapse and let user handle this.
