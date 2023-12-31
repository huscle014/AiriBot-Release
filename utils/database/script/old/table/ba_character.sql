CREATE TABLE IF NOT EXISTS `BA_CHARACTER` (
	`ID` INTEGER PRIMARY KEY AUTOINCREMENT,
	`C_AVATAR` VARCHAR(512) DEFAULT '',
	`C_NAME` VARCHAR(120) DEFAULT '',
	`C_RARITY` INT DEFAULT '0',
	`C_SCHOOL` VARCHAR(100) DEFAULT '',
	`C_ROLE` VARCHAR(100) DEFAULT '',
	`C_POSITION` VARCHAR(100) DEFAULT '',
	`C_ATTACK_TYPE` VARCHAR(100) DEFAULT '',
	`C_ARMOR_TYPE` VARCHAR(100) DEFAULT '',
	`C_COMBAT_CLASS` VARCHAR(100) DEFAULT '',
	`C_WEAPON` VARCHAR(100) DEFAULT '',
	`C_COVER` VARCHAR(30) DEFAULT '',
	`C_URBAN` VARCHAR(5) DEFAULT '',
	`C_OUTDOORS` VARCHAR(5) DEFAULT '',
	`C_INDOORS` VARCHAR(5) DEFAULT '',
	`C_RELEASE_DATE` VARCHAR(50) DEFAULT '',
    `CREATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`CREATED_BY` VARCHAR(20),
	`UPDATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`UPDATED_BY` VARCHAR(20),
	UNIQUE('C_NAME', 'C_RARITY')
);