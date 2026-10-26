CREATE DATABASE IF NOT EXISTS agroflow_inventory
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE agroflow_inventory;

-- Elimina las tablas antiguas de inventario; los datos diarios se conservan.
DROP TABLE IF EXISTS cerdas, gallinas, vacas;

-- Cuentas utilizadas para iniciar sesión y relacionar registros.
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'student') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT IGNORE INTO usuarios (username, password_hash, role) VALUES
(
    'adminiecamd',
    'scrypt:32768:8:1$b63v9IAFWNnqnbMF$db1195ebfc2a8fca478fa75bd3b553cfb5b9063eb323bff1e37b94dcd11c8f886ba1522097cc47dcbb58d23c5544df368c19b26c99a4a10db7b72fddc48db6fc',
    'admin'
),
(
    'estudianteiecamd',
    'scrypt:32768:8:1$Loow4v0NLpsesGv6$de3013c1f57d4aca621d4787199106d6f17ab1add5ef575ebe9b4eb701947990afd56bc40343f0bd9c2daaf768827ecb31fa19840f21395c52fe9b69fc4b0b3a',
    'student'
);

-- Apartado: Gallinas.
CREATE TABLE IF NOT EXISTS gallinas_diario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATE NOT NULL,
    edad_semanas INT NOT NULL DEFAULT 0,
    aves_vivas INT NOT NULL DEFAULT 0,
    huevos_recogidos INT NOT NULL DEFAULT 0,
    huevos_comerciales INT NOT NULL DEFAULT 0,
    huevos_rotos INT NOT NULL DEFAULT 0,
    huevos_sucios INT NOT NULL DEFAULT 0,
    huevos_cama INT NOT NULL DEFAULT 0,
    porcentaje_postura DECIMAL(7, 2) NOT NULL DEFAULT 0,
    mortalidad INT NOT NULL DEFAULT 0,
    alimento_kg DECIMAL(9, 2) NOT NULL DEFAULT 0,
    consumo_ave_dia_g DECIMAL(9, 2) NOT NULL DEFAULT 0,
    observaciones TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_gallinas_diario_fecha (fecha)
) ENGINE=InnoDB;

-- Apartado: Cerdas.
CREATE TABLE IF NOT EXISTS porcino_partos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_cerda VARCHAR(30) NOT NULL,
    fecha_parto DATE NOT NULL,
    hora_inicio TIME,
    hora_finaliza TIME,
    n_lechones INT NOT NULL DEFAULT 0,
    machos INT NOT NULL DEFAULT 0,
    hembras INT NOT NULL DEFAULT 0,
    concentrado_lechones_kg DECIMAL(10, 3)
        GENERATED ALWAYS AS (n_lechones * 0.500) STORED,
    mantenimiento_cerda_kg DECIMAL(10, 3) NOT NULL DEFAULT 2.000,
    total_diario_kg DECIMAL(10, 3)
        GENERATED ALWAYS AS (n_lechones * 0.500 + mantenimiento_cerda_kg) STORED,
    total_levante_2_meses_kg DECIMAL(12, 3)
        GENERATED ALWAYS AS ((n_lechones * 0.500 + mantenimiento_cerda_kg) * 60) STORED,
    INDEX idx_porcino_partos_fecha (fecha_parto)
) ENGINE=InnoDB;

-- Apartado: Vacas.
CREATE TABLE IF NOT EXISTS vacas_alimento_diario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATE NOT NULL,
    cantidad_kg DECIMAL(10, 3) NOT NULL,
    leche_litros DECIMAL(10, 3) NOT NULL DEFAULT 0,
    observaciones TEXT,
    usuario_id INT NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_vacas_alimento_fecha (fecha),
    CONSTRAINT fk_vacas_alimento_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

-- Apartado: Plantas.
CREATE TABLE IF NOT EXISTS plantas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Apartado: Alimento (compras por especie).
CREATE TABLE IF NOT EXISTS compras_alimento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    especie ENUM('gallinas', 'cerdos', 'vacas') NOT NULL,
    cantidad_kg DECIMAL(10, 3) NOT NULL,
    fecha_compra DATE NOT NULL,
    observaciones TEXT,
    admin_id INT NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_compras_alimento_especie_fecha (especie, fecha_compra),
    CONSTRAINT fk_compra_alimento_admin
        FOREIGN KEY (admin_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;
