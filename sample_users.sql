-- Sample professor users
INSERT INTO public.users (auth_id, email, role) VALUES
    ('11111111-1111-1111-1111-111111111111', 'john.doe@university.edu' 'professor'),
    ('22222222-2222-2222-2222-222222222222', 'jane.smith@university.edu', 'professor'),
    ('33333333-3333-3333-3333-333333333333', 'robert.wilson@university.edu', 'professor');

-- Sample student users
INSERT INTO public.users (auth_id, email, role) VALUES
    ('44444444-4444-4444-4444-444444444444', 'alice.johnson@student.university.edu', 'student'),
    ('55555555-5555-5555-5555-555555555555', 'bob.williams@student.university.edu', 'student'),
    ('66666666-6666-6666-6666-666666666666', 'charlie.brown@student.university.edu', 'student'),
    ('77777777-7777-7777-7777-777777777777', 'diana.miller@student.university.edu', 'student'),
    ('88888888-8888-8888-8888-888888888888', 'edward.davis@student.university.edu', 'student'); 