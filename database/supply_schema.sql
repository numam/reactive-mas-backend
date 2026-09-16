-- Skema database Halal Supply Chain Ayam
-- Jalankan di HeidiSQL setelah memilih database `supply`.
-- Engine InnoDB dipakai agar foreign key dan transaksi aktif.

CREATE DATABASE IF NOT EXISTS `supply`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `supply`;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `retail_stock`, `rph_wholesaler_contract`,
  `wholesaler_retail_contract`, `shipment_item`, `batch_flock_source`,
  `farm_supplier`, `inspection`, `shipment`, `product`, `slaughter_batch`,
  `flock`, `slaughterman`, `vehicle`, `retail`, `wholesaler`,
  `slaughterhouse`, `farm`, `supplier`, `halal_certificate`;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `halal_certificate` (
  `cert_id` VARCHAR(15) PRIMARY KEY,
  `cert_number` VARCHAR(30) NOT NULL,
  `issuer` VARCHAR(80) NOT NULL,
  `entity_type` ENUM('supplier','farm','rph','wholesaler','retail','vehicle') NOT NULL,
  `valid_from` DATE NOT NULL,
  `valid_until` DATE NOT NULL,
  `status` ENUM('aktif','kadaluarsa','dicabut') NOT NULL DEFAULT 'aktif',
  `document_url` VARCHAR(255),
  UNIQUE KEY `uq_certificate_number` (`cert_number`),
  CHECK (`valid_until` >= `valid_from`)
) ENGINE=InnoDB;

CREATE TABLE `supplier` (
  `supplier_id` VARCHAR(12) PRIMARY KEY,
  `supplier_name` VARCHAR(100) NOT NULL,
  `supplier_type` ENUM('doc','pakan','obat_vaksin') NOT NULL,
  `address` VARCHAR(200) NOT NULL,
  `province` VARCHAR(50) NOT NULL,
  `phone` VARCHAR(15),
  `cert_id` VARCHAR(15),
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT `fk_supplier_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `farm` (
  `farm_id` VARCHAR(12) PRIMARY KEY,
  `farm_name` VARCHAR(100) NOT NULL,
  `owner_name` VARCHAR(100) NOT NULL,
  `farm_type` ENUM('mandiri','mitra','integrator') NOT NULL,
  `address` VARCHAR(200) NOT NULL,
  `latitude` DECIMAL(9,6) NOT NULL,
  `longitude` DECIMAL(9,6) NOT NULL,
  `capacity_head` INT UNSIGNED NOT NULL,
  `cage_type` ENUM('open_house','closed_house') NOT NULL,
  `cert_id` VARCHAR(15),
  `phone` VARCHAR(15),
  CONSTRAINT `fk_farm_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `slaughterhouse` (
  `rph_id` VARCHAR(12) PRIMARY KEY,
  `rph_name` VARCHAR(100) NOT NULL,
  `address` VARCHAR(200) NOT NULL,
  `latitude` DECIMAL(9,6) NOT NULL,
  `longitude` DECIMAL(9,6) NOT NULL,
  `capacity_per_day` INT UNSIGNED NOT NULL,
  `facility_type` ENUM('modern','semi_modern','tradisional') NOT NULL,
  `nkv_number` VARCHAR(30) NOT NULL,
  `cert_id` VARCHAR(15),
  CONSTRAINT `fk_rph_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `wholesaler` (
  `wholesaler_id` VARCHAR(12) PRIMARY KEY,
  `wholesaler_name` VARCHAR(100) NOT NULL,
  `address` VARCHAR(200) NOT NULL,
  `latitude` DECIMAL(9,6) NOT NULL,
  `longitude` DECIMAL(9,6) NOT NULL,
  `storage_capacity_kg` INT UNSIGNED NOT NULL,
  `storage_temp_c` DECIMAL(4,1) NOT NULL,
  `cert_id` VARCHAR(15),
  CONSTRAINT `fk_wholesaler_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `retail` (
  `retail_id` VARCHAR(12) PRIMARY KEY,
  `retail_name` VARCHAR(100) NOT NULL,
  `outlet_type` ENUM('supermarket','minimarket','pasar_tradisional','online') NOT NULL,
  `address` VARCHAR(200) NOT NULL,
  `latitude` DECIMAL(9,6) NOT NULL,
  `longitude` DECIMAL(9,6) NOT NULL,
  `cert_id` VARCHAR(15),
  `phone` VARCHAR(15),
  CONSTRAINT `fk_retail_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `vehicle` (
  `vehicle_id` VARCHAR(12) PRIMARY KEY,
  `plate_number` VARCHAR(15) NOT NULL UNIQUE,
  `vehicle_type` ENUM('livestock_truck','refrigerated_truck','box_pickup') NOT NULL,
  `owner_id` VARCHAR(12) NOT NULL,
  `owner_type` ENUM('farm','rph','wholesaler') NOT NULL,
  `min_temp_c` DECIMAL(4,1),
  `cert_id` VARCHAR(15),
  CONSTRAINT `fk_vehicle_certificate` FOREIGN KEY (`cert_id`) REFERENCES `halal_certificate` (`cert_id`)
) ENGINE=InnoDB;

CREATE TABLE `slaughterman` (
  `slaughterman_id` VARCHAR(12) PRIMARY KEY,
  `rph_id` VARCHAR(12) NOT NULL,
  `full_name` VARCHAR(100) NOT NULL,
  `juleha_cert_number` VARCHAR(30) NOT NULL UNIQUE,
  `cert_valid_until` DATE NOT NULL,
  `status` ENUM('aktif','nonaktif','cuti') NOT NULL DEFAULT 'aktif',
  CONSTRAINT `fk_slaughterman_rph` FOREIGN KEY (`rph_id`) REFERENCES `slaughterhouse` (`rph_id`)
) ENGINE=InnoDB;

CREATE TABLE `flock` (
  `flock_id` VARCHAR(18) PRIMARY KEY,
  `farm_id` VARCHAR(12) NOT NULL,
  `doc_supplier_id` VARCHAR(12) NOT NULL,
  `breed` VARCHAR(50) NOT NULL,
  `placement_date` DATE NOT NULL,
  `initial_qty` INT UNSIGNED NOT NULL,
  `mortality_qty` INT UNSIGNED NOT NULL DEFAULT 0,
  `avg_weight_kg` DECIMAL(5,2),
  `harvest_date` DATE,
  `withdrawal_ok` BOOLEAN NOT NULL DEFAULT FALSE,
  `status` ENUM('aktif','panen','gagal') NOT NULL DEFAULT 'aktif',
  CONSTRAINT `fk_flock_farm` FOREIGN KEY (`farm_id`) REFERENCES `farm` (`farm_id`),
  CONSTRAINT `fk_flock_supplier` FOREIGN KEY (`doc_supplier_id`) REFERENCES `supplier` (`supplier_id`)
) ENGINE=InnoDB;

CREATE TABLE `slaughter_batch` (
  `batch_id` VARCHAR(20) PRIMARY KEY,
  `rph_id` VARCHAR(12) NOT NULL,
  `slaughterman_id` VARCHAR(12) NOT NULL,
  `slaughter_datetime` DATETIME NOT NULL,
  `qty_head` INT UNSIGNED NOT NULL,
  `total_carcass_kg` DECIMAL(10,2) NOT NULL,
  `slaughter_method` ENUM('manual','mekanik') NOT NULL,
  `stunning_used` BOOLEAN NOT NULL DEFAULT FALSE,
  `ante_mortem_pass` BOOLEAN NOT NULL,
  `post_mortem_pass` BOOLEAN NOT NULL,
  `halal_status` ENUM('halal','ditolak','ditahan') NOT NULL,
  CONSTRAINT `fk_batch_rph` FOREIGN KEY (`rph_id`) REFERENCES `slaughterhouse` (`rph_id`),
  CONSTRAINT `fk_batch_slaughterman` FOREIGN KEY (`slaughterman_id`) REFERENCES `slaughterman` (`slaughterman_id`)
) ENGINE=InnoDB;

CREATE TABLE `product` (
  `product_id` VARCHAR(20) PRIMARY KEY,
  `batch_id` VARCHAR(20) NOT NULL,
  `product_type` ENUM('karkas_utuh','fillet','paha','sayap','sayap_beku') NOT NULL,
  `packaging_type` ENUM('frozen','chilled') NOT NULL,
  `net_weight_kg` DECIMAL(8,2) NOT NULL,
  `production_date` DATE NOT NULL,
  `expiry_date` DATE NOT NULL,
  `halal_label_code` VARCHAR(30) NOT NULL,
  CONSTRAINT `fk_product_batch` FOREIGN KEY (`batch_id`) REFERENCES `slaughter_batch` (`batch_id`),
  CHECK (`expiry_date` >= `production_date`)
) ENGINE=InnoDB;

CREATE TABLE `shipment` (
  `shipment_id` CHAR(36) PRIMARY KEY,
  `vehicle_id` VARCHAR(12) NOT NULL,
  `origin_id` VARCHAR(12) NOT NULL,
  `origin_type` ENUM('farm','rph','wholesaler') NOT NULL,
  `destination_id` VARCHAR(12) NOT NULL,
  `destination_type` ENUM('rph','wholesaler','retail') NOT NULL,
  `departure_time` DATETIME NOT NULL,
  `estimated_arrival` DATETIME NOT NULL,
  `actual_arrival` DATETIME,
  `avg_temp_c` DECIMAL(4,1),
  `temp_breach` BOOLEAN NOT NULL DEFAULT FALSE,
  `status` ENUM('dijadwalkan','transit','tiba','ditolak') NOT NULL DEFAULT 'dijadwalkan',
  CONSTRAINT `fk_shipment_vehicle` FOREIGN KEY (`vehicle_id`) REFERENCES `vehicle` (`vehicle_id`)
) ENGINE=InnoDB;

CREATE TABLE `inspection` (
  `inspection_id` VARCHAR(15) PRIMARY KEY,
  `entity_id` VARCHAR(12) NOT NULL,
  `entity_type` ENUM('farm','rph','wholesaler','retail') NOT NULL,
  `inspector_agency` VARCHAR(80) NOT NULL,
  `inspection_date` DATE NOT NULL,
  `score` DECIMAL(4,2) NOT NULL,
  `finding` VARCHAR(255),
  `result` ENUM('lulus','lulus_bersyarat','tidak_lulus') NOT NULL,
  CHECK (`score` BETWEEN 1 AND 10)
) ENGINE=InnoDB;

CREATE TABLE `farm_supplier` (
  `farm_id` VARCHAR(12) NOT NULL,
  `supplier_id` VARCHAR(12) NOT NULL,
  `supply_type` ENUM('doc','pakan','obat_vaksin') NOT NULL,
  `contract_start` DATE NOT NULL,
  `contract_end` DATE,
  PRIMARY KEY (`farm_id`, `supplier_id`),
  CONSTRAINT `fk_farm_supplier_farm` FOREIGN KEY (`farm_id`) REFERENCES `farm` (`farm_id`),
  CONSTRAINT `fk_farm_supplier_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `supplier` (`supplier_id`)
) ENGINE=InnoDB;

CREATE TABLE `batch_flock_source` (
  `batch_id` VARCHAR(20) NOT NULL,
  `flock_id` VARCHAR(18) NOT NULL,
  `qty_head` INT UNSIGNED NOT NULL,
  `received_datetime` DATETIME NOT NULL,
  PRIMARY KEY (`batch_id`, `flock_id`),
  CONSTRAINT `fk_source_batch` FOREIGN KEY (`batch_id`) REFERENCES `slaughter_batch` (`batch_id`),
  CONSTRAINT `fk_source_flock` FOREIGN KEY (`flock_id`) REFERENCES `flock` (`flock_id`)
) ENGINE=InnoDB;

CREATE TABLE `shipment_item` (
  `shipment_id` CHAR(36) NOT NULL,
  `product_id` VARCHAR(20) NOT NULL,
  `qty_package` INT UNSIGNED NOT NULL,
  `total_weight_kg` DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (`shipment_id`, `product_id`),
  CONSTRAINT `fk_item_shipment` FOREIGN KEY (`shipment_id`) REFERENCES `shipment` (`shipment_id`),
  CONSTRAINT `fk_item_product` FOREIGN KEY (`product_id`) REFERENCES `product` (`product_id`)
) ENGINE=InnoDB;

CREATE TABLE `wholesaler_retail_contract` (
  `wholesaler_id` VARCHAR(12) NOT NULL,
  `retail_id` VARCHAR(12) NOT NULL,
  `start_date` DATE NOT NULL,
  `delivery_frequency` ENUM('harian','mingguan','sesuai_pesanan') NOT NULL,
  `status` ENUM('aktif','berakhir','ditangguhkan') NOT NULL DEFAULT 'aktif',
  PRIMARY KEY (`wholesaler_id`, `retail_id`),
  CONSTRAINT `fk_contract_wholesaler` FOREIGN KEY (`wholesaler_id`) REFERENCES `wholesaler` (`wholesaler_id`),
  CONSTRAINT `fk_contract_retail` FOREIGN KEY (`retail_id`) REFERENCES `retail` (`retail_id`)
) ENGINE=InnoDB;

CREATE TABLE `rph_wholesaler_contract` (
  `rph_id` VARCHAR(12) NOT NULL,
  `wholesaler_id` VARCHAR(12) NOT NULL,
  `start_date` DATE NOT NULL,
  `monthly_quota_kg` INT UNSIGNED NOT NULL,
  `status` ENUM('aktif','berakhir') NOT NULL DEFAULT 'aktif',
  PRIMARY KEY (`rph_id`, `wholesaler_id`),
  CONSTRAINT `fk_rph_contract_rph` FOREIGN KEY (`rph_id`) REFERENCES `slaughterhouse` (`rph_id`),
  CONSTRAINT `fk_rph_contract_wholesaler` FOREIGN KEY (`wholesaler_id`) REFERENCES `wholesaler` (`wholesaler_id`)
) ENGINE=InnoDB;

CREATE TABLE `retail_stock` (
  `retail_id` VARCHAR(12) NOT NULL,
  `product_id` VARCHAR(20) NOT NULL,
  `stock_qty_kg` DECIMAL(10,2) NOT NULL DEFAULT 0,
  `min_stock_kg` DECIMAL(10,2) NOT NULL DEFAULT 0,
  `selling_price` DECIMAL(12,2) NOT NULL,
  `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`retail_id`, `product_id`),
  CONSTRAINT `fk_stock_retail` FOREIGN KEY (`retail_id`) REFERENCES `retail` (`retail_id`),
  CONSTRAINT `fk_stock_product` FOREIGN KEY (`product_id`) REFERENCES `product` (`product_id`)
) ENGINE=InnoDB;
