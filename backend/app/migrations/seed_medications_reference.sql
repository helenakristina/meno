-- Seed: medications_reference
-- Initial system-curated MHT medications. All rows have is_user_created=FALSE
-- and created_by=NULL, so they are readable by all authenticated users.
-- Run after the add_mht_medication_tracking.sql migration.

INSERT INTO medications_reference
    (brand_name, generic_name, hormone_type, common_forms, common_doses, notes, is_user_created)
VALUES

-- ============================================================
-- ESTROGEN
-- ============================================================
('Climara',      'estradiol', 'estrogen',
 ARRAY['patch'],
 ARRAY['0.025mg', '0.0375mg', '0.05mg', '0.075mg', '0.1mg'],
 'Applied once weekly', FALSE),

('Vivelle-Dot',  'estradiol', 'estrogen',
 ARRAY['patch'],
 ARRAY['0.025mg', '0.0375mg', '0.05mg', '0.075mg', '0.1mg'],
 'Applied twice weekly', FALSE),

('Estrace',      'estradiol', 'estrogen',
 ARRAY['pill', 'cream'],
 ARRAY['0.5mg', '1mg', '2mg'],
 NULL, FALSE),

('Divigel',      'estradiol', 'estrogen',
 ARRAY['gel'],
 ARRAY['0.25mg', '0.5mg', '1.0mg'],
 'Applied once daily to upper thigh', FALSE),

('EstroGel',     'estradiol', 'estrogen',
 ARRAY['gel'],
 ARRAY['0.75mg/pump'],
 '1 pump = 0.75mg; applied once daily', FALSE),

('Evamist',      'estradiol', 'estrogen',
 ARRAY['spray'],
 ARRAY['1.53mg/spray'],
 'Applied to inner forearm', FALSE),

('Femring',      'estradiol acetate', 'estrogen',
 ARRAY['ring'],
 ARRAY['0.05mg/day', '0.1mg/day'],
 'Vaginal ring; replaced every 3 months', FALSE),

('Estring',      'estradiol', 'estrogen',
 ARRAY['ring'],
 ARRAY['2mg (7.5mcg/day)'],
 'Vaginal/local only; replaced every 90 days', FALSE),

('Vagifem',      'estradiol', 'estrogen',
 ARRAY['vaginal tablet'],
 ARRAY['10mcg'],
 'Also sold as Yuvafem; vaginal/local only', FALSE),

('Premarin',     'conjugated estrogens', 'estrogen',
 ARRAY['pill', 'cream'],
 ARRAY['0.3mg', '0.45mg', '0.625mg', '0.9mg', '1.25mg'],
 NULL, FALSE),

-- ============================================================
-- PROGESTERONE / PROGESTINS
-- ============================================================
('Prometrium',   'micronized progesterone', 'progesterone',
 ARRAY['pill'],
 ARRAY['100mg', '200mg'],
 'Can be taken orally or vaginally', FALSE),

('Provera',      'medroxyprogesterone acetate', 'progestin',
 ARRAY['pill'],
 ARRAY['2.5mg', '5mg', '10mg'],
 NULL, FALSE),

('Mirena',       'levonorgestrel', 'progestin',
 ARRAY['other'],
 ARRAY['52mg (releases ~20mcg/day)'],
 'Hormonal IUD; lasts up to 8 years', FALSE),

('Endometrin',   'progesterone', 'progesterone',
 ARRAY['other'],
 ARRAY['100mg'],
 'Vaginal insert', FALSE),

-- ============================================================
-- COMBINATION (estrogen + progestin)
-- ============================================================
('Prempro',      'conjugated estrogens / medroxyprogesterone acetate', 'combination',
 ARRAY['pill'],
 ARRAY['0.3mg/1.5mg', '0.45mg/1.5mg', '0.625mg/2.5mg', '0.625mg/5mg'],
 NULL, FALSE),

('Activella',    'estradiol / norethindrone acetate', 'combination',
 ARRAY['pill'],
 ARRAY['0.5mg/0.1mg', '1mg/0.5mg'],
 NULL, FALSE),

('CombiPatch',   'estradiol / norethindrone acetate', 'combination',
 ARRAY['patch'],
 ARRAY['0.05mg/0.14mg', '0.05mg/0.25mg'],
 'Applied twice weekly', FALSE),

('Bijuva',       'estradiol / progesterone', 'combination',
 ARRAY['pill'],
 ARRAY['1mg/100mg'],
 'Bioidentical combination', FALSE),

-- ============================================================
-- TESTOSTERONE
-- ============================================================
('AndroGel (off-label)', 'testosterone', 'testosterone',
 ARRAY['gel'],
 ARRAY['Varies (titrated to female ranges)'],
 'Off-label for women; dose typically 1/10th of male dose', FALSE),

(NULL, 'Compounded testosterone', 'testosterone',
 ARRAY['cream', 'gel', 'pellet', 'troche'],
 ARRAY['0.5mg/day', '1mg/day', '2mg/day'],
 'Compounded formulations; dose varies widely by provider and lab', FALSE)

ON CONFLICT DO NOTHING;
