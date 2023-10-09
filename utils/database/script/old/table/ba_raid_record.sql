DROP TABLE IF EXISTS BA_RAID_RECORD;

CREATE TABLE IF NOT EXISTS `BA_RAID_RECORD` (
	`ID` INTEGER PRIMARY KEY AUTOINCREMENT,
	`R_ID` INTEGER,
	`R_NAME` VARCHAR(100) DEFAULT '',
	`R_START_DATE` DATETIME,
	`R_END_DATE` DATETIME,
	`R_TYPE` VARCHAR(100),
	`R_SEASON` VARCHAR(100),
    `CREATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`CREATED_BY` VARCHAR(20),
	`UPDATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`UPDATED_BY` VARCHAR(20),
	UNIQUE(R_ID, R_SEASON)
);
