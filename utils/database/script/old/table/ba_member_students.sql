CREATE TABLE IF NOT EXISTS `BA_MEMBER_STUDENTS` (
	`MEMBER_ID` INT,
	`C_NAME` VARCHAR(120),
    `RARITY` TEXT(4) DEFAULT '',
	`SKILL_EX` TEXT(1) DEFAULT '',
	`SKILL_NORMAL` TEXT(1) DEFAULT '',
	`SKILL_PASSIVE` TEXT(1) DEFAULT '',
	`SKILL_SUB` TEXT(1) DEFAULT '',
    `CREATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`CREATED_BY` VARCHAR(20),
	`UPDATED_ON` DATETIME DEFAULT CURRENT_TIMESTAMP,
	`UPDATED_BY` VARCHAR(20),
	UNIQUE('MEMBER_ID', 'C_NAME')
);