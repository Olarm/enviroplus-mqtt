using TimesDates, TimeZones, Dates, SQLite, DataFrames
using LibPQ



function first()
	db = SQLite.DB("enviro.db")
	df = DBInterface.execute(db, "select * from enviro order by timestamp") |> DataFrame
	
	df.timestamp = replace.(df.timestamp, " " => "T")
	df.timestamp = TimeDateZone.(df.timestamp)
	
	return df
end


function second(df, conn_str)
	conn = LibPQ.Connection(conn_str)
	for row in eachrow(df)
		ts = row.timestamp
		temp = row.temperature
		pres = row.pressure
		hum = row.humidity
		oxi = row.oxidised
		red = row.reduced
		nh3 = row.nh3
		lux = row.lux
		query = """
		INSERT INTO 
			enviro (
				timestamp,
				temperature,
				pressure,
				humidity,
				oxidised,
				reduced,
				nh3,
				lux
			)
			values (
				$ts,
				$temp,
				$pres,
				$hum,
				$oxi,
				$red,
				$nh3,
				$lux
			);
		"""
		execute(conn, query)
	end
end
