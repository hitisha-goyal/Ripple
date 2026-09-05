-- Grade bands. Kept small on purpose: it exists so the repository holds a
-- table that no chain from the tracked column ever reaches.
CREATE TABLE IF NOT EXISTS reference.grade_scale (
  grade_code STRING,
  grade_label STRING,
  min_weight_kg NUMERIC
);
