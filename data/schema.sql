/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-11.8.8-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: nmap_api_v1
-- ------------------------------------------------------
-- Server version	11.8.8-MariaDB-ubu2404-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `allocation_failures`
--

DROP TABLE IF EXISTS `allocation_failures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `allocation_failures` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(50) DEFAULT NULL,
  `error_msg` varchar(255) DEFAULT NULL,
  `kst_time` datetime DEFAULT NULL,
  `ip` varchar(45) DEFAULT NULL,
  `payload` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=22075 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `daily_progress`
--

DROP TABLE IF EXISTS `daily_progress`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `daily_progress` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `work_date` date NOT NULL,
  `site_id` varchar(20) NOT NULL,
  `dest_id` varchar(50) NOT NULL,
  `sid` bigint(20) NOT NULL,
  `total_target` int(11) DEFAULT 0,
  `success_cnt` int(11) DEFAULT 0,
  `fail_cnt` int(11) DEFAULT 0,
  `last_success_at` datetime DEFAULT NULL,
  `last_fail_at` datetime DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `alloc_fail_cnt` int(11) DEFAULT 0,
  `last_dist_m` int(11) DEFAULT 800 COMMENT '금일 마지막 성공 거리(m)',
  `miss_cnt` int(11) DEFAULT 0,
  `timeout_cnt` int(11) DEFAULT 0,
  `mismatch_cnt` int(11) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_date_site_sid` (`work_date`,`site_id`,`sid`),
  KEY `idx_dest_date` (`dest_id`,`work_date`)
) ENGINE=InnoDB AUTO_INCREMENT=433846 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `daily_stats`
--

DROP TABLE IF EXISTS `daily_stats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `daily_stats` (
  `work_date` date NOT NULL,
  `total_target` int(11) DEFAULT 0,
  `success_cnt` int(11) DEFAULT 0,
  `fail_cnt` int(11) DEFAULT 0,
  `pending_places` int(11) DEFAULT 0,
  `verified_places` int(11) DEFAULT 0,
  `fail_places` int(11) DEFAULT 0,
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`work_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device_daily_stats`
--

DROP TABLE IF EXISTS `device_daily_stats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_daily_stats` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(50) NOT NULL,
  `work_date` date NOT NULL,
  `success_cnt` int(11) DEFAULT 0,
  `fail_cnt` int(11) DEFAULT 0,
  `alloc_fail_cnt` int(11) DEFAULT 0,
  `total_duration_sec` int(11) DEFAULT 0,
  `last_active_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_device_date` (`device_id`,`work_date`),
  KEY `idx_date` (`work_date`)
) ENGINE=InnoDB AUTO_INCREMENT=2957921 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device_ip_rotation_logs`
--

DROP TABLE IF EXISTS `device_ip_rotation_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_ip_rotation_logs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(50) NOT NULL,
  `prev_ip` varchar(45) DEFAULT NULL,
  `new_ip` varchar(45) NOT NULL,
  `changed_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_device_changed` (`device_id`,`changed_at`)
) ENGINE=InnoDB AUTO_INCREMENT=13563 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `devices`
--

DROP TABLE IF EXISTS `devices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `devices` (
  `seq` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(50) NOT NULL,
  `status` enum('on','off') DEFAULT 'on',
  `alias` varchar(50) DEFAULT NULL,
  `orig_ssaid` varchar(64) DEFAULT NULL,
  `orig_adid` varchar(64) DEFAULT NULL,
  `orig_idfv` varchar(64) DEFAULT NULL,
  `orig_ni` varchar(64) DEFAULT NULL,
  `orig_token` varchar(64) DEFAULT NULL,
  `current_ip` varchar(45) DEFAULT NULL,
  `ip_updated_at` datetime DEFAULT NULL,
  `hostname` varchar(60) DEFAULT NULL,
  `is_alert_muted` tinyint(1) NOT NULL DEFAULT 0,
  `install_place` varchar(100) DEFAULT NULL,
  `install_count` int(11) DEFAULT 1,
  `network_type` varchar(20) DEFAULT 'wired',
  PRIMARY KEY (`seq`),
  UNIQUE KEY `seq` (`seq`),
  UNIQUE KEY `idx_device_id` (`device_id`)
) ENGINE=InnoDB AUTO_INCREMENT=602 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fail_log`
--

DROP TABLE IF EXISTS `fail_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `fail_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `log_id` int(11) DEFAULT NULL,
  `device_id` varchar(50) DEFAULT NULL,
  `dest_id` varchar(20) DEFAULT NULL,
  `fail_status` varchar(255) DEFAULT NULL,
  `requested_address` varchar(255) DEFAULT NULL,
  `actual_address` varchar(255) DEFAULT NULL,
  `error_msg` text DEFAULT NULL,
  `log_path` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6246 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ip_allocation_history`
--

DROP TABLE IF EXISTS `ip_allocation_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ip_allocation_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip` varchar(50) NOT NULL,
  `dest_id` varchar(50) NOT NULL,
  `allocated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_allocated_at` (`allocated_at`),
  KEY `idx_ip_dest_date` (`ip`,`dest_id`,`allocated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=60581 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ip_success_history`
--

DROP TABLE IF EXISTS `ip_success_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ip_success_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip` varchar(45) NOT NULL,
  `dest_id` varchar(50) NOT NULL,
  `last_success_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_last_success` (`last_success_at`),
  KEY `idx_ip_dest` (`ip`,`dest_id`)
) ENGINE=InnoDB AUTO_INCREMENT=241766 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `keyword_allocation_failures`
--

DROP TABLE IF EXISTS `keyword_allocation_failures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `keyword_allocation_failures` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `work_date` date NOT NULL,
  `site_id` varchar(20) DEFAULT NULL,
  `dest_id` varchar(50) DEFAULT NULL,
  `dest_name` varchar(255) DEFAULT NULL,
  `search_keyword` varchar(255) DEFAULT NULL,
  `device_id` varchar(50) DEFAULT NULL,
  `last_dist_m` int(11) DEFAULT NULL,
  `last_rank` int(11) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_date` (`work_date`),
  KEY `idx_dest` (`dest_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4662 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `lte_data_usage`
--

DROP TABLE IF EXISTS `lte_data_usage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `lte_data_usage` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `modem_name` varchar(100) NOT NULL,
  `work_date` date NOT NULL,
  `init_upload` bigint(20) DEFAULT 0,
  `init_download` bigint(20) DEFAULT 0,
  `now_upload` bigint(20) DEFAULT 0,
  `now_download` bigint(20) DEFAULT 0,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_modem_date` (`modem_name`,`work_date`)
) ENGINE=InnoDB AUTO_INCREMENT=344 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `optimizer_success_logs`
--

DROP TABLE IF EXISTS `optimizer_success_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `optimizer_success_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dest_id` varchar(50) NOT NULL,
  `site_id` varchar(20) NOT NULL,
  `keyword` varchar(255) NOT NULL,
  `lat` decimal(9,7) NOT NULL,
  `lng` decimal(10,7) NOT NULL,
  `distance_m` int(11) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_dest_created` (`dest_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=550 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `place_keywords`
--

DROP TABLE IF EXISTS `place_keywords`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `place_keywords` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dest_id` varchar(50) NOT NULL,
  `keyword` varchar(255) NOT NULL,
  `status` enum('on','off') DEFAULT 'on',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_dest_id` (`dest_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `places`
--

DROP TABLE IF EXISTS `places`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `places` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dest_id` varchar(50) NOT NULL,
  `name` varchar(255) NOT NULL,
  `address` varchar(255) DEFAULT NULL,
  `original_address` varchar(255) DEFAULT NULL,
  `lat` decimal(9,7) DEFAULT NULL,
  `lng` decimal(10,7) DEFAULT NULL,
  `arr_min_s` int(11) DEFAULT 300 COMMENT '최소 주행 시간 (초)',
  `arr_max_s` int(11) DEFAULT 480 COMMENT '최대 주행 시간 (초)',
  `dist_min_m` int(11) DEFAULT 1000 COMMENT '출발지 최소 거리 (m)',
  `dist_max_m` int(11) DEFAULT 10000 COMMENT '출발지 최대 거리 (m)',
  `check_status` varchar(20) DEFAULT 'PENDING',
  `last_checked_at` datetime DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `is_optimizer` tinyint(4) DEFAULT 0 COMMENT '할당 시 실시간 가시거리 체크 여부 (1: 체크함, 0: 안함)',
  `fail_count` int(11) DEFAULT 0,
  `last_optimized_at` datetime DEFAULT NULL COMMENT '마지막 가시거리 정밀 점검 시간',
  `optimization_priority` int(11) DEFAULT 0 COMMENT '우선순위 (높을수록 먼저 점검)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_dest_id` (`dest_id`),
  KEY `idx_is_optimizer` (`is_optimizer`),
  KEY `idx_check_status` (`check_status`)
) ENGINE=InnoDB AUTO_INCREMENT=48688088 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `raw_slots`
--

DROP TABLE IF EXISTS `raw_slots`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `raw_slots` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `site_id` varchar(20) NOT NULL,
  `sid` bigint(20) NOT NULL,
  `dest_id` varchar(50) NOT NULL,
  `search_keyword` varchar(255) DEFAULT '',
  `target_url` text DEFAULT NULL,
  `work_count` int(11) NOT NULL DEFAULT 0,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `status` enum('on','off') DEFAULT 'on',
  `is_deleted` tinyint(4) DEFAULT 0,
  `deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `config_hash` varchar(32) DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_site_sid` (`site_id`,`sid`),
  KEY `idx_dest_id` (`dest_id`),
  KEY `idx_dest_status` (`dest_id`,`status`)
) ENGINE=InnoDB AUTO_INCREMENT=41796 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `slot_changelog`
--

DROP TABLE IF EXISTS `slot_changelog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slot_changelog` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `site_id` varchar(20) NOT NULL,
  `slot_id` bigint(20) NOT NULL,
  `change_type` varchar(20) NOT NULL,
  `changed_column` varchar(50) DEFAULT NULL,
  `old_value` text DEFAULT NULL,
  `new_value` text DEFAULT NULL,
  `changed_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_site_slot` (`site_id`,`slot_id`)
) ENGINE=InnoDB AUTO_INCREMENT=92054 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sync_log_detail`
--

DROP TABLE IF EXISTS `sync_log_detail`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sync_log_detail` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `summary_id` bigint(20) NOT NULL,
  `site_id` varchar(20) NOT NULL,
  `sid` varchar(50) NOT NULL,
  `action_type` enum('INSERT','UPDATE','DELETE') NOT NULL,
  `old_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`old_data`)),
  `new_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`new_data`)),
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_summary_id` (`summary_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sync_log_summary`
--

DROP TABLE IF EXISTS `sync_log_summary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sync_log_summary` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `site_id` varchar(20) NOT NULL,
  `sync_time` datetime NOT NULL,
  `total_fetched` int(11) NOT NULL,
  `inserted_cnt` int(11) NOT NULL DEFAULT 0,
  `updated_cnt` int(11) NOT NULL DEFAULT 0,
  `deleted_cnt` int(11) NOT NULL DEFAULT 0,
  `error_msg` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=64 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system_metrics`
--

DROP TABLE IF EXISTS `system_metrics`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_metrics` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `heartbeat_at` timestamp NULL DEFAULT current_timestamp(),
  `cpu_usage` float DEFAULT NULL,
  `ram_usage_mb` float DEFAULT NULL,
  `disk_free_gb` float DEFAULT NULL,
  `disk_total_gb` float DEFAULT NULL,
  `active_devices` int(11) DEFAULT NULL,
  `total_req` int(11) DEFAULT NULL,
  `net_sent_mb` float DEFAULT NULL,
  `net_recv_mb` float DEFAULT NULL,
  `db_pool_used` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8110 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `task_position_pool`
--

DROP TABLE IF EXISTS `task_position_pool`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `task_position_pool` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dest_id` varchar(50) NOT NULL,
  `lat` double NOT NULL,
  `lng` double NOT NULL,
  `dist_m` int(11) NOT NULL,
  `is_used` tinyint(4) DEFAULT 0,
  `created_date` date NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `keyword` varchar(255) DEFAULT NULL,
  `total_place_count` int(11) DEFAULT NULL,
  `autocomplete_count` int(11) DEFAULT NULL,
  `actual_rank` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_dest_date_used` (`dest_id`,`created_date`,`is_used`)
) ENGINE=InnoDB AUTO_INCREMENT=57557 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tasks_log`
--

DROP TABLE IF EXISTS `tasks_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tasks_log` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `work_date` date NOT NULL,
  `site_id` varchar(20) NOT NULL,
  `sid` varchar(50) NOT NULL,
  `dest_id` varchar(50) NOT NULL,
  `dest_name` varchar(255) DEFAULT NULL,
  `device_id` varchar(50) NOT NULL,
  `ip` varchar(45) DEFAULT NULL,
  `spoofed_identity` text DEFAULT NULL,
  `distance_m` int(11) DEFAULT 0,
  `speed_kmh` decimal(5,2) DEFAULT NULL,
  `client_dist_m` int(11) DEFAULT 0,
  `client_time_s` int(11) DEFAULT 0,
  `client_speed_kmh` decimal(5,2) DEFAULT NULL,
  `duration_sec` int(11) DEFAULT 0,
  `start_time` timestamp NULL DEFAULT current_timestamp(),
  `end_time` timestamp NULL DEFAULT NULL,
  `status` varchar(255) NOT NULL DEFAULT 'WORKING',
  `result_msg` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_date_site_sid` (`work_date`,`site_id`,`sid`),
  KEY `idx_device` (`device_id`),
  KEY `idx_dest_id` (`dest_id`),
  KEY `idx_status` (`status`),
  KEY `idx_ip_status` (`ip`,`status`),
  KEY `idx_device_id_id` (`device_id`,`id`)
) ENGINE=InnoDB AUTO_INCREMENT=384556 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary table structure for view `v_lte_today_usage`
--

DROP TABLE IF EXISTS `v_lte_today_usage`;
/*!50001 DROP VIEW IF EXISTS `v_lte_today_usage`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_lte_today_usage` AS SELECT
 NULL AS `id`,
 NULL AS `modem_name`,
 NULL AS `work_date`,
 NULL AS `total_used_gb` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `view_today_allocation`
--

DROP TABLE IF EXISTS `view_today_allocation`;
/*!50001 DROP VIEW IF EXISTS `view_today_allocation`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `view_today_allocation` AS SELECT
 NULL AS `daily_pk`,
 NULL AS `site_id`,
 NULL AS `sid`,
 NULL AS `dest_id`,
 NULL AS `name`,
 NULL AS `address`,
 NULL AS `lat`,
 NULL AS `lng`,
 NULL AS `arr_min_s`,
 NULL AS `arr_max_s`,
 NULL AS `dist_min_m`,
 NULL AS `dist_max_m`,
 NULL AS `check_status`,
 NULL AS `is_optimizer`,
 NULL AS `total_target`,
 NULL AS `total_success`,
 NULL AS `remain_count`,
 NULL AS `last_success_at`,
 NULL AS `last_fail_at` */;
SET character_set_client = @saved_cs_client;

--
-- Dumping routines for database 'nmap_api_v1'
--

--
-- Final view structure for view `v_lte_today_usage`
--

/*!50001 DROP VIEW IF EXISTS `v_lte_today_usage`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`nmap`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_lte_today_usage` AS select `lte_data_usage`.`id` AS `id`,`lte_data_usage`.`modem_name` AS `modem_name`,`lte_data_usage`.`work_date` AS `work_date`,round((`lte_data_usage`.`now_upload` - `lte_data_usage`.`init_upload` + (`lte_data_usage`.`now_download` - `lte_data_usage`.`init_download`)) / 1073741824,2) AS `total_used_gb` from `lte_data_usage` where `lte_data_usage`.`work_date` = curdate() order by round((`lte_data_usage`.`now_upload` - `lte_data_usage`.`init_upload` + (`lte_data_usage`.`now_download` - `lte_data_usage`.`init_download`)) / 1073741824,2) desc */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `view_today_allocation`
--

/*!50001 DROP VIEW IF EXISTS `view_today_allocation`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_uca1400_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`nmap`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `view_today_allocation` AS select `dp`.`id` AS `daily_pk`,`s`.`site_id` AS `site_id`,min(`s`.`sid`) AS `sid`,`s`.`dest_id` AS `dest_id`,`p`.`name` AS `name`,`p`.`address` AS `address`,`p`.`lat` AS `lat`,`p`.`lng` AS `lng`,`p`.`arr_min_s` AS `arr_min_s`,`p`.`arr_max_s` AS `arr_max_s`,`p`.`dist_min_m` AS `dist_min_m`,`p`.`dist_max_m` AS `dist_max_m`,`p`.`check_status` AS `check_status`,`p`.`is_optimizer` AS `is_optimizer`,sum(`s`.`work_count`) AS `total_target`,ifnull(`dp`.`success_cnt`,0) AS `total_success`,sum(`s`.`work_count`) - ifnull(`dp`.`success_cnt`,0) AS `remain_count`,`dp`.`last_success_at` AS `last_success_at`,`dp`.`last_fail_at` AS `last_fail_at` from ((`raw_slots` `s` left join `places` `p` on(`s`.`dest_id` = `p`.`dest_id`)) left join `daily_progress` `dp` on(`s`.`site_id` = `dp`.`site_id` and `s`.`dest_id` = `dp`.`dest_id` and `dp`.`work_date` = curdate())) where `s`.`status` = 'on' and curdate() between `s`.`start_date` and `s`.`end_date` and (`p`.`check_status` is null or `p`.`check_status` <> 'FAIL') group by `s`.`site_id`,`s`.`dest_id` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-06-28 13:37:48
