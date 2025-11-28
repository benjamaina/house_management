-- query to show all tables in my database
SELECT table_name FROM information_schema.tables WHERE table_schema='public';
SELECT * FROM django_migrations;