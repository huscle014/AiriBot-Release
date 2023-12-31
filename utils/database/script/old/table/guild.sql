CREATE TABLE IF NOT EXISTS `BA_GUILD` (
	`SERVER_ID` INT,
	`GUILD_ID` INT,
	`GUILD_NAME` VARCHAR(100),
	`GUILD_DESCRIPTION` VARCHAR(100),
	`DEFAULT_ROLE` INT DEFAULT 0,
	`RAID_TOP_ROLE` INT DEFAULT 0,
	`RAID_THRESHOLD` INT DEFAULT 0,
	`CONFIGURED_BY` INT,
	`CREATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`CREATED_BY` VARCHAR(20),
	`UPDATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`UPDATED_BY` VARCHAR(20),
	PRIMARY KEY (`SERVER_ID`,`GUILD_ID`),
	UNIQUE (`SERVER_ID`,`GUILD_ID`)
);