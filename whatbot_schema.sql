CREATE TABLE album
( id integer primary key autoincrement
, artist text
, title text
, year text
, torrent text
);
CREATE TABLE format
( id integer primary key autoincrement
, album_id integer
, format text
, bitrate text
, source text
, edition text
, seeds text
, size text
, scene integer
, freeleech integer
, url text
);
CREATE TABLE request
( request_id integer not null
, request_name varchar(255) not null
, reward numeric not null
, filled varchar(3) not null
, torrent_group_id integer
, flac_present varchar2(3)
, primary key (request_id)
);
CREATE TABLE request_artist
( request_id integer not null
, artist_id integer not null
, artist_name varchar(255) not null
, primary key (request_id, artist_id)
, foreign key (request_id) references request(request_id)
);
CREATE TABLE request_tag
( request_id integer not null
, tag varchar(40) not null
, primary key (request_id, tag)
, foreign key (request_id) references request(request_id)
);
CREATE INDEX format_idx01 on format(album_id);
