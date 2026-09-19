-- LiftPortal: схема для MySQL 8 (utf8mb4). Создаётся автоматически и при первом запуске приложения.
-- CREATE DATABASE liftportal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE audit_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	user_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	entity VARCHAR(40) NOT NULL, 
	entity_id INTEGER, 
	details JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE tenants (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	slug VARCHAR(64) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	legal_name VARCHAR(200) NOT NULL, 
	tagline JSON NOT NULL, 
	about JSON NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	country VARCHAR(80) NOT NULL, 
	address VARCHAR(255) NOT NULL, 
	phone VARCHAR(64) NOT NULL, 
	phone2 VARCHAR(64) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	website VARCHAR(200) NOT NULL, 
	founded_year INTEGER, 
	idno VARCHAR(32) NOT NULL, 
	custom_domain VARCHAR(160) NOT NULL, 
	default_locale VARCHAR(2) NOT NULL, 
	locales JSON NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	vat_rate FLOAT NOT NULL, 
	plan VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	is_listed BOOL NOT NULL, 
	profile VARCHAR(40) NOT NULL, 
	theme JSON NOT NULL, 
	hero JSON NOT NULL, 
	faq JSON NOT NULL, 
	social JSON NOT NULL, 
	smtp JSON NOT NULL, 
	storage JSON NOT NULL, 
	pricing JSON NOT NULL, 
	settings JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	email VARCHAR(160) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	full_name VARCHAR(160) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	locale VARCHAR(2) NOT NULL, 
	is_platform_admin BOOL NOT NULL, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_login_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE cases (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	title JSON NOT NULL, 
	body JSON NOT NULL, 
	client_name VARCHAR(160) NOT NULL, 
	location VARCHAR(160) NOT NULL, 
	year INTEGER, 
	metrics JSON NOT NULL, 
	image_url VARCHAR(600) NOT NULL, 
	is_published BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE domains (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	host VARCHAR(160) NOT NULL, 
	is_primary BOOL NOT NULL, 
	verified BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	UNIQUE (host)
);

CREATE TABLE equipment_categories (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	name JSON NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	sort INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE invites (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	partner_id INTEGER, 
	token VARCHAR(64) NOT NULL, 
	used_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	UNIQUE (token)
);

CREATE TABLE media (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	backend VARCHAR(16) NOT NULL, 
	`key` VARCHAR(400) NOT NULL, 
	url VARCHAR(600) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	mime VARCHAR(80) NOT NULL, 
	size INTEGER NOT NULL, 
	alt JSON NOT NULL, 
	tags VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE outbox (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	to_email VARCHAR(160) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	transport VARCHAR(40) NOT NULL, 
	error TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE pages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	title JSON NOT NULL, 
	body JSON NOT NULL, 
	in_menu BOOL NOT NULL, 
	is_published BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE partners (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	idno VARCHAR(32) NOT NULL, 
	contact_name VARCHAR(160) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	tier VARCHAR(16) NOT NULL, 
	discount_pct FLOAT NOT NULL, 
	credit_limit FLOAT NOT NULL, 
	payment_days INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	turnover FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE products (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	sku VARCHAR(60) NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	title JSON NOT NULL, 
	description JSON NOT NULL, 
	attributes JSON NOT NULL, 
	unit VARCHAR(16) NOT NULL, 
	price FLOAT NOT NULL, 
	stock FLOAT NOT NULL, 
	made_to_order BOOL NOT NULL, 
	is_published BOOL NOT NULL, 
	image_url VARCHAR(600) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE reviews (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	order_id INTEGER, 
	author VARCHAR(120) NOT NULL, 
	rating INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	reply TEXT NOT NULL, 
	is_published BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE services (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	icon VARCHAR(8) NOT NULL, 
	title JSON NOT NULL, 
	short JSON NOT NULL, 
	body JSON NOT NULL, 
	price_from FLOAT NOT NULL, 
	pricing_model VARCHAR(20) NOT NULL, 
	is_orderable BOOL NOT NULL, 
	is_published BOOL NOT NULL, 
	image_url VARCHAR(600) NOT NULL, 
	sort INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE contacts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	user_id INTEGER, 
	partner_id INTEGER, 
	kind VARCHAR(10) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	company VARCHAR(160) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	tags VARCHAR(200) NOT NULL, 
	notes TEXT NOT NULL, 
	orders_count INTEGER NOT NULL, 
	revenue FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(partner_id) REFERENCES partners (id) ON DELETE SET NULL
);

CREATE TABLE equipment (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	category_id INTEGER, 
	slug VARCHAR(120) NOT NULL, 
	inventory_no VARCHAR(40) NOT NULL, 
	brand VARCHAR(80) NOT NULL, 
	model VARCHAR(120) NOT NULL, 
	title JSON NOT NULL, 
	description JSON NOT NULL, 
	year INTEGER, 
	status VARCHAR(20) NOT NULL, 
	is_published BOOL NOT NULL, 
	capacity_t FLOAT NOT NULL, 
	radius_m FLOAT NOT NULL, 
	height_m FLOAT NOT NULL, 
	outrigger_half_m FLOAT NOT NULL, 
	payload_kg FLOAT NOT NULL, 
	platform_l_mm FLOAT NOT NULL, 
	platform_w_mm FLOAT NOT NULL, 
	spec JSON NOT NULL, 
	hourly_rate FLOAT NOT NULL, 
	min_hours FLOAT NOT NULL, 
	mobilization_fee FLOAT NOT NULL, 
	per_km_rate FLOAT NOT NULL, 
	photo_url VARCHAR(600) NOT NULL, 
	gallery JSON NOT NULL, 
	sort INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES equipment_categories (id) ON DELETE SET NULL
);

CREATE TABLE memberships (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	partner_id INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_membership UNIQUE (tenant_id, user_id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(partner_id) REFERENCES partners (id) ON DELETE SET NULL
);

CREATE TABLE projects (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	partner_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	address VARCHAR(255) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	starts_at DATE, 
	ends_at DATE, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(partner_id) REFERENCES partners (id) ON DELETE CASCADE
);

CREATE TABLE bookings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	equipment_id INTEGER NOT NULL, 
	starts_at DATETIME NOT NULL, 
	ends_at DATETIME NOT NULL, 
	reason VARCHAR(20) NOT NULL, 
	order_id INTEGER, 
	note VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(equipment_id) REFERENCES equipment (id) ON DELETE CASCADE
);

CREATE TABLE load_charts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	equipment_id INTEGER NOT NULL, 
	configuration VARCHAR(80) NOT NULL, 
	outriggers VARCHAR(12) NOT NULL, 
	radius_m FLOAT NOT NULL, 
	capacity_t FLOAT NOT NULL, 
	height_m FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(equipment_id) REFERENCES equipment (id) ON DELETE CASCADE
);

CREATE TABLE orders (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	number VARCHAR(24) NOT NULL, 
	contact_id INTEGER, 
	partner_id INTEGER, 
	project_id INTEGER, 
	equipment_id INTEGER, 
	service_id INTEGER, 
	assignee_id INTEGER, 
	kind VARCHAR(10) NOT NULL, 
	source VARCHAR(30) NOT NULL, 
	stage VARCHAR(16) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	task_type VARCHAR(40) NOT NULL, 
	cargo VARCHAR(200) NOT NULL, 
	weight_t FLOAT NOT NULL, 
	height_m FLOAT NOT NULL, 
	radius_m FLOAT NOT NULL, 
	conditions JSON NOT NULL, 
	address VARCHAR(255) NOT NULL, 
	zone VARCHAR(40) NOT NULL, 
	distance_km FLOAT NOT NULL, 
	starts_at DATETIME, 
	hours FLOAT NOT NULL, 
	flexible_date BOOL NOT NULL, 
	price_min FLOAT NOT NULL, 
	price_max FLOAT NOT NULL, 
	price_final FLOAT NOT NULL, 
	breakdown JSON NOT NULL, 
	escalated BOOL NOT NULL, 
	escalation_reasons JSON NOT NULL, 
	selector_log JSON NOT NULL, 
	comment TEXT NOT NULL, 
	internal_note TEXT NOT NULL, 
	payment_status VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES contacts (id) ON DELETE SET NULL, 
	FOREIGN KEY(partner_id) REFERENCES partners (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
	FOREIGN KEY(equipment_id) REFERENCES equipment (id) ON DELETE SET NULL, 
	FOREIGN KEY(service_id) REFERENCES services (id) ON DELETE SET NULL, 
	FOREIGN KEY(assignee_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE activities (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	order_id INTEGER, 
	contact_id INTEGER, 
	user_id INTEGER, 
	kind VARCHAR(16) NOT NULL, 
	body TEXT NOT NULL, 
	due_at DATETIME, 
	done BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE documents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	order_id INTEGER, 
	partner_id INTEGER, 
	type VARCHAR(16) NOT NULL, 
	number VARCHAR(32) NOT NULL, 
	amount FLOAT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	issued_at DATE NOT NULL, 
	due_at DATE, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
);

CREATE TABLE shifts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER NOT NULL, 
	order_id INTEGER NOT NULL, 
	project_id INTEGER, 
	equipment_id INTEGER, 
	work_date DATE NOT NULL, 
	operator VARCHAR(120) NOT NULL, 
	hours_worked FLOAT NOT NULL, 
	hours_idle FLOAT NOT NULL, 
	idle_fault VARCHAR(16) NOT NULL, 
	lifts INTEGER NOT NULL, 
	notes TEXT NOT NULL, 
	photos JSON NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	dispute_reason TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
	FOREIGN KEY(equipment_id) REFERENCES equipment (id) ON DELETE SET NULL
);
