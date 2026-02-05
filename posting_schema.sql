-- posting_schema.sql (MySQL 8.0)
-- 64 sharded posting tables: code_postings_00 .. code_postings_3f
-- shard = fp & 0x3f

SET sql_notes = 0;

DROP TABLE IF EXISTS stop_fingerprints;
CREATE TABLE stop_fingerprints (
  fp BIGINT UNSIGNED NOT NULL,
  df INT NOT NULL,
  PRIMARY KEY (fp),
  KEY idx_df (df)
) ENGINE=InnoDB;

-- Create 64 tables
-- Each table uses a compact PK to avoid an extra AUTO_INCREMENT column.
-- PK(fp, order_id, pos) is typically unique for one doc.
-- idx_order_pos supports alignment/segment extraction during rerank.
DROP TABLE IF EXISTS code_postings_00;
CREATE TABLE code_postings_00 (
  fp BIGINT UNSIGNED NOT NULL,
  order_id INT NOT NULL,
  pos INT NOT NULL,
  start_line INT NOT NULL,
  end_line INT NOT NULL,
  PRIMARY KEY (fp, order_id, pos),
  KEY idx_order_pos (order_id, pos)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS code_postings_01;
CREATE TABLE code_postings_01 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_02;
CREATE TABLE code_postings_02 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_03;
CREATE TABLE code_postings_03 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_04;
CREATE TABLE code_postings_04 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_05;
CREATE TABLE code_postings_05 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_06;
CREATE TABLE code_postings_06 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_07;
CREATE TABLE code_postings_07 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_08;
CREATE TABLE code_postings_08 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_09;
CREATE TABLE code_postings_09 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0a;
CREATE TABLE code_postings_0a LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0b;
CREATE TABLE code_postings_0b LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0c;
CREATE TABLE code_postings_0c LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0d;
CREATE TABLE code_postings_0d LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0e;
CREATE TABLE code_postings_0e LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_0f;
CREATE TABLE code_postings_0f LIKE code_postings_00;

DROP TABLE IF EXISTS code_postings_10;
CREATE TABLE code_postings_10 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_11;
CREATE TABLE code_postings_11 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_12;
CREATE TABLE code_postings_12 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_13;
CREATE TABLE code_postings_13 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_14;
CREATE TABLE code_postings_14 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_15;
CREATE TABLE code_postings_15 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_16;
CREATE TABLE code_postings_16 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_17;
CREATE TABLE code_postings_17 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_18;
CREATE TABLE code_postings_18 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_19;
CREATE TABLE code_postings_19 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1a;
CREATE TABLE code_postings_1a LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1b;
CREATE TABLE code_postings_1b LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1c;
CREATE TABLE code_postings_1c LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1d;
CREATE TABLE code_postings_1d LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1e;
CREATE TABLE code_postings_1e LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_1f;
CREATE TABLE code_postings_1f LIKE code_postings_00;

DROP TABLE IF EXISTS code_postings_20;
CREATE TABLE code_postings_20 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_21;
CREATE TABLE code_postings_21 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_22;
CREATE TABLE code_postings_22 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_23;
CREATE TABLE code_postings_23 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_24;
CREATE TABLE code_postings_24 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_25;
CREATE TABLE code_postings_25 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_26;
CREATE TABLE code_postings_26 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_27;
CREATE TABLE code_postings_27 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_28;
CREATE TABLE code_postings_28 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_29;
CREATE TABLE code_postings_29 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2a;
CREATE TABLE code_postings_2a LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2b;
CREATE TABLE code_postings_2b LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2c;
CREATE TABLE code_postings_2c LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2d;
CREATE TABLE code_postings_2d LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2e;
CREATE TABLE code_postings_2e LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_2f;
CREATE TABLE code_postings_2f LIKE code_postings_00;

DROP TABLE IF EXISTS code_postings_30;
CREATE TABLE code_postings_30 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_31;
CREATE TABLE code_postings_31 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_32;
CREATE TABLE code_postings_32 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_33;
CREATE TABLE code_postings_33 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_34;
CREATE TABLE code_postings_34 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_35;
CREATE TABLE code_postings_35 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_36;
CREATE TABLE code_postings_36 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_37;
CREATE TABLE code_postings_37 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_38;
CREATE TABLE code_postings_38 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_39;
CREATE TABLE code_postings_39 LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3a;
CREATE TABLE code_postings_3a LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3b;
CREATE TABLE code_postings_3b LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3c;
CREATE TABLE code_postings_3c LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3d;
CREATE TABLE code_postings_3d LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3e;
CREATE TABLE code_postings_3e LIKE code_postings_00;
DROP TABLE IF EXISTS code_postings_3f;
CREATE TABLE code_postings_3f LIKE code_postings_00;

SET sql_notes = 1;