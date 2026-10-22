"""
Consultas del reporte de carga (ERP ATENEA2, BBDD GRUPO).
Son exactamente las cinco consultas validadas de la pestaña del ERP.
Cada una se ejecuta por separado y devuelve filas (dict).
"""

# 1. GRID PRINCIPAL
GRID_PRINCIPAL = r"""
SELECT
    Fecha,
    SUM(CASE WHEN Preparada = 1 AND Unidad = 'M2' THEN Cantidad ELSE 0 END) AS M2P,
    SUM(CASE WHEN Preparada = 1 AND Unidad = 'PZ' THEN Cantidad ELSE 0 END) AS PzP,
    SUM(CASE WHEN Preparada = 1 AND Unidad = 'UD' THEN Cantidad ELSE 0 END) AS UdP,
    SUM(CASE WHEN Preparada = 1 THEN PaletsC  ELSE 0 END) AS PcP,
    SUM(CASE WHEN Preparada = 1 THEN Picos    ELSE 0 END) AS PiP,
    SUM(CASE WHEN Preparada = 1 THEN Piezas   ELSE 0 END) AS PzP1,
    SUM(CASE WHEN Preparada = 1 THEN Muestras ELSE 0 END) AS MuP,
    SUM(CASE WHEN Preparada = 1 THEN ComSer   ELSE 0 END) AS CSP,
    SUM(CASE WHEN Preparada = 1 THEN Cliente  ELSE 0 END) AS ClP,
    SUM(CASE WHEN TipoC = 'AD' AND Unidad = 'M2' THEN Cantidad ELSE 0 END) AS M2A,
    SUM(CASE WHEN TipoC = 'AD' AND Unidad = 'PZ' THEN Cantidad ELSE 0 END) AS PzA,
    SUM(CASE WHEN TipoC = 'AD' AND Unidad = 'UD' THEN Cantidad ELSE 0 END) AS UdA,
    SUM(CASE WHEN TipoC = 'AD' THEN PaletsC  ELSE 0 END) AS PcA,
    SUM(CASE WHEN TipoC = 'AD' THEN Picos    ELSE 0 END) AS PiA,
    SUM(CASE WHEN TipoC = 'AD' THEN Piezas   ELSE 0 END) AS PzA1,
    SUM(CASE WHEN TipoC = 'AD' THEN Muestras ELSE 0 END) AS MuA,
    SUM(CASE WHEN TipoC = 'AD' THEN ComSer   ELSE 0 END) AS CSA,
    SUM(CASE WHEN TipoC = 'AD' THEN Cliente  ELSE 0 END) AS ClA,
    SUM(CASE WHEN Unidad = 'M2' THEN Cantidad ELSE 0 END) AS M2T,
    SUM(CASE WHEN Unidad = 'PZ' THEN Cantidad ELSE 0 END) AS PzT,
    SUM(CASE WHEN Unidad = 'UD' THEN Cantidad ELSE 0 END) AS UdT,
    SUM(PaletsC)  AS PcT,
    SUM(Picos)    AS PiT,
    SUM(Piezas)   AS PzT1,
    SUM(Muestras) AS MuT,
    SUM(ComSer)   AS CST,
    SUM(Cliente)  AS ClT,
    CAST(COUNT(DISTINCT IdCarga) / 177.0 * 100.0 AS smallint) AS Cuenta
FROM (
    SELECT
        Fecha, Unidad, Cantidad, PaletsC, TipoC, IdCarga, Preparada,
        CASE WHEN ClasePico = 'CS' THEN Pico ELSE 0 END AS ComSer,
        CASE WHEN ClasePico = 'CL' THEN Pico ELSE 0 END AS Cliente,
        CASE WHEN ClasePico = 'MU' THEN Pico ELSE 0 END AS Muestras,
        CASE WHEN ClasePico = 'PZ' THEN Pico ELSE 0 END AS Piezas,
        CASE WHEN ClasePico = 'PI' THEN Pico ELSE 0 END AS Picos
    FROM (
        SELECT
            CONVERT(datetime, CONVERT(char, CASE WHEN ISNULL(b.stnEstadoFecha,0) = 9 THEN '01/01/1990 00:00' ELSE b.FechaCarga END, 1), 1) AS Fecha,
            d.atrUnidad AS Unidad,
            c.atrCantidad * -1 AS Cantidad,
            CAST(ROUND(-1*c.atrCantidad/d.atrDimension/h.atrCajasBulto/h.atrNroElementos, 0, 1)
                 + CASE WHEN ABS((-1*c.atrCantidad/d.atrDimension/h.atrCajasBulto/h.atrNroElementos) - ROUND(-1*c.atrCantidad/d.atrDimension/h.atrCajasBulto/h.atrNroElementos, 0)) BETWEEN 0.000000001 AND 0.001 THEN 1 ELSE 0 END
                 AS smallint) AS PaletsC,
            CASE WHEN ABS((-1*c.atrCantidad/d.atrDimension/h.atrCajasBulto/h.atrNroElementos) - ROUND(-1*c.atrCantidad/d.atrDimension/h.atrCajasBulto/h.atrNroElementos, 0)) > 0.001 THEN 1 ELSE 0 END AS Pico,
            CASE WHEN RIGHT(d.atrReferencia,1) IN ('E','F')   THEN 'CS'
                 WHEN d.atrIdCaracteristica4 IN ('3','4')     THEN 'CL'
                 WHEN RIGHT(a.atrIdTipoOC,1) = 'M'            THEN 'MU'
                 WHEN d.atrUnidad <> 'M2'                     THEN 'PZ'
                 ELSE 'PI' END AS ClasePico,
            b.Tipo AS TipoC,
            b.IdCarga,
            CASE WHEN c.stnPreparado = 1 THEN 1 ELSE 0 END AS Preparada
        FROM cmCargaConfirmada_OCs a
        INNER JOIN cmCargaConfirmada b    ON a.IdCarga = b.IdCarga
        INNER JOIN entOC_DETALLE c        ON a.atrIdOrdenCarga = c.atrIdOrdenCarga AND a.atrIdTipoOC = c.atrIdTipoOC
        INNER JOIN entARTICULO d          ON c.atrReferencia = d.atrReferencia
        INNER JOIN entORDENCARGA e        ON e.atrIdTipoOC = c.atrIdTipoOC AND e.atrIdOrdenCarga = c.atrIdOrdenCarga
        INNER JOIN entEMBALAJE_ARTICULO h ON h.atrReferencia = d.atrReferencia AND c.stnIdEmbalaje = h.atrIdEmbalaje
    ) base
) clasif
GROUP BY Fecha
ORDER BY Fecha
"""

# 2. Fila "Cargado"
CARGADO = r"""
SELECT
    ISNULL(SUM(CASE WHEN c.atrUnidad = 'M2' THEN a.atrCantidad * -1 ELSE 0 END), 0) AS metros,
    ISNULL(SUM(CASE WHEN c.atrUnidad = 'PZ' THEN a.atrCantidad * -1 ELSE 0 END), 0) AS piezas,
    CASE puntocarga
        WHEN 'A' THEN 'AL' WHEN '2' THEN 'AL'
        WHEN 'K' THEN 'KE' WHEN 'C' THEN 'CL'
        WHEN 'X' THEN 'C2' WHEN '3' THEN 'C3'
        WHEN 'W' THEN 'VI' WHEN '8' THEN 'C8'
        ELSE 'ST'
    END AS centro
FROM entMOVIMIENTO a
INNER JOIN entALBARAN b         ON a.atrIdTipoMovimiento = b.atrIdTipoMovimiento AND a.atrIdAlbaran = b.atrIdAlbaran
INNER JOIN entARTICULO c        ON a.atrReferencia = c.atrReferencia
INNER JOIN entOC_DETALLE d      ON d.atrIdAlbaran = a.atrIdAlbaran AND d.atrIdTipoMovimiento = a.atrIdTipoMovimiento AND d.atrLineaAlbaran = a.atrLinea
INNER JOIN entORDENCARGA e      ON d.atrIdTipoOC = e.atrIdTipoOC AND d.atrIdOrdenCarga = e.atrIdOrdenCarga
LEFT JOIN ExpLineaExpedicion f  ON d.atrIdOrdenCarga = f.atrIdOrdenCarga AND d.atrIdTipoOC = f.atrIdTipoOC AND d.atrLineaOC = f.atrLineaOC
LEFT JOIN ExpExpedicion g       ON f.IdExpedicion = g.IdExpedicion
WHERE CAST(b.atrAlbaranFecha AS date) = CAST(GETDATE() AS date)
  AND RIGHT(a.atrIdTipoMovimiento, 2) IN ('XN','SN','XE','SE')
GROUP BY
    CASE puntocarga
        WHEN 'A' THEN 'AL' WHEN '2' THEN 'AL'
        WHEN 'K' THEN 'KE' WHEN 'C' THEN 'CL'
        WHEN 'X' THEN 'C2' WHEN '3' THEN 'C3'
        WHEN 'W' THEN 'VI' WHEN '8' THEN 'C8'
        ELSE 'ST'
    END
"""

# 3. Fila "En proceso" (usa cursor + tabla temporal; SET NOCOUNT para no romper el fetch)
EN_PROCESO = r"""
SET NOCOUNT ON;
DECLARE @ocs TABLE (atrIdTipoOC varchar(3) NOT NULL, atrIdOrdenCarga int NOT NULL, metros money, piezas int, almacen varchar(3));
DECLARE @oc varchar(1000), @almacen varchar(3), @ocactual varchar(20), @occadena varchar(1000), @ocnum int, @octxt varchar(20),
        @octipo varchar(3), @indice int, @metros money, @piezas int;

DECLARE micursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT a.oc, b.almacen
    FROM cmCargaConfirmadaLogs a
    INNER JOIN StnERPCONFColas b ON a.Tipo = b.IDCola
    WHERE TipoAccion = 'Borrado desde expedición'
      AND CONVERT(datetime, CONVERT(char, FechaAccion, 1), 1) = CONVERT(datetime, CONVERT(char, GETDATE(), 1), 1)
    UNION
    SELECT a.oc, b.almacen COLLATE SQL_Latin1_General_CP1_CI_AS
    FROM STN_OC_ENPROCESO_CARGA a
    INNER JOIN stnSCALE_almacenes b ON a.warehouse COLLATE SQL_Latin1_General_CP1_CI_AS = b.almacenscale;

OPEN micursor;
FETCH NEXT FROM micursor INTO @oc, @almacen;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @occadena = @oc;
    WHILE @occadena <> ''
    BEGIN
        SET @indice   = CHARINDEX(';', @occadena);
        SET @ocactual = LEFT(@occadena, @indice - 1);
        SET @occadena = SUBSTRING(@occadena, @indice + 1, LEN(@occadena) - @indice);

        SET @octipo = LEFT(@ocactual, 3);
        SET @octxt  = REPLACE(@ocactual, '.', '');
        SET @octxt  = RIGHT(@octxt, LEN(@octxt) - 3);
        SET @ocnum  = CASE WHEN ISNUMERIC(@octxt) = 1 THEN CAST(@octxt AS int) ELSE 0 END;

        SELECT @metros = ISNULL(SUM(CASE WHEN b.atrUnidad = 'M2' AND c.atrServido = 0 THEN a.atrCantidad * -1 ELSE 0 END), 0),
               @piezas = ISNULL(SUM(CASE WHEN b.atrUnidad = 'PZ' AND c.atrServido = 0 THEN a.atrCantidad * -1 ELSE 0 END), 0)
        FROM entOC_DETALLE a
        INNER JOIN entARTICULO b   ON a.atrReferencia = b.atrReferencia
        INNER JOIN entORDENCARGA c ON a.atrIdTipoOC = c.atrIdTipoOC AND a.atrIdOrdenCarga = c.atrIdOrdenCarga
        WHERE a.atrIdTipoOC = @octipo AND a.atrIdOrdenCarga = @ocnum;

        INSERT INTO @ocs VALUES (@octipo, @ocnum, @metros, @piezas, @almacen);
    END
    FETCH NEXT FROM micursor INTO @oc, @almacen;
END
CLOSE micursor;
DEALLOCATE micursor;

SELECT ISNULL(SUM(metros), 0) AS metros, ISNULL(SUM(piezas), 0) AS piezas, almacen
FROM @ocs
WHERE RIGHT(atrIdTipoOC, 2) <> 'OM'
GROUP BY almacen;
"""

# 4. Fila "Producto"
PRODUCTO = r"""
SELECT
    b.atrUnidad AS UD,
    SUM(CASE WHEN b.atrIdCaracteristica1 NOT IN ('4','5','9','11','13') THEN a.atrAlStock ELSE 0 END) AS STN,
    SUM(CASE WHEN b.atrIdCaracteristica1 = '4'         THEN a.atrAlStock ELSE 0 END) AS ALA,
    SUM(CASE WHEN b.atrIdCaracteristica1 IN ('5','11') THEN a.atrAlStock ELSE 0 END) AS KER,
    SUM(CASE WHEN b.atrIdCaracteristica1 = '9'         THEN a.atrAlStock ELSE 0 END) AS VIT,
    SUM(CASE WHEN b.atrIdCaracteristica1 = '13'        THEN a.atrAlStock ELSE 0 END) AS VNX
FROM entALMACEN_LOTE a
INNER JOIN entARTICULO b ON a.atrReferencia = b.atrReferencia
WHERE a.atrIdAlmacen IN ('01','OC')
  AND a.atrNumeroLote <> 'STFC'
  AND b.atrUnidad IN ('M2','PZ')
GROUP BY b.atrUnidad
"""

# 5. Fila "Almacén"
ALMACEN = r"""
SELECT
    a.almacenrumbo AS situacionerp,
    b.atrUnidad,
    SUM(a.atrCantidad) AS tot
FROM stn_stock_sga a
INNER JOIN entARTICULO b ON a.atrReferencia = b.atrReferencia
WHERE b.atrUnidad IN ('M2','PZ')
GROUP BY a.almacenrumbo, b.atrUnidad
"""
