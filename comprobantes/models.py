# gestion/comprobantes/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction


class Comprobante(models.Model):
    TIPO_COMPROBANTE = [
        ("PRES", "Presupuesto"),
        ("REMI", "Remito Interno"),
    ]


    # ⭐⭐ ESTE ES UN REGISTRO DE CONFIGURACIÓN, NO UN DOCUMENTO
    # Controla la numeración para un tipo+serie específico
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_COMPROBANTE,
        default="PRES",
        help_text="Tipo de comprobante que controla esta configuración"
    )
   
    serie = models.CharField(
        max_length=5,
        default="00001",
        help_text="Serie (punto de venta/sucursal)"
    )
   
    # ⭐⭐ RANGO DE NUMERACIÓN
    numero_inicial = models.IntegerField(
        default=1,
        help_text="Primer número del rango"
    )
   
    numero_final = models.IntegerField(
        help_text="Último número del rango"
    )
   
    # ⭐⭐ PRÓXIMO NÚMERO A USAR - MODIFICABLE MANUALMENTE
    proximo_numero = models.IntegerField(
        default=1,
        help_text="Próximo número a usar. Puede ajustarse manualmente si hubo documentos fuera del sistema."
    )


    class Meta:
        # ⭐⭐ SOLO UN REGISTRO POR TIPO+SERIE
        unique_together = ('tipo', 'serie')
        verbose_name = "Configuración de Numeración"
        verbose_name_plural = "Configuraciones de Numeración"
        indexes = [
            models.Index(fields=['tipo', 'serie']),
        ]


    def clean(self):
        """Validaciones de datos"""
        # Validación EXTRA: Asegurar que no sean strings con nombres de campo
        campos_a_validar = [
            ('proximo_numero', 'próximo número'),
            ('numero_inicial', 'número inicial'), 
            ('numero_final', 'número final')
        ]
        
        for campo, nombre_amigable in campos_a_validar:
            valor = getattr(self, campo)
            
            # Si es string, verificar que sea un número válido
            if isinstance(valor, str):
                valor_limpio = valor.strip()
                
                # ❌ NO PERMITIR que sea el nombre del campo
                if valor_limpio.lower() == campo.lower() or valor_limpio.lower() == nombre_amigable.lower():
                    raise ValidationError(
                        f"El campo '{nombre_amigable}' no puede contener el texto '{valor}'. "
                        f"Debe ser un número válido."
                    )
                
                # Verificar que sea convertible a número
                try:
                    float(valor_limpio)
                except ValueError:
                    raise ValidationError(
                        f"El campo '{nombre_amigable}' debe ser un número válido. "
                        f"Valor actual: '{valor}'"
                    )
        
        # Asegurar que los valores sean integers antes de validar
        try:
            if self.numero_final is not None:
                self.numero_final = int(self.numero_final)
        except (TypeError, ValueError):
            raise ValidationError("El número final debe ser un valor numérico")
        
        try:
            if self.numero_inicial is not None:
                self.numero_inicial = int(self.numero_inicial)
        except (TypeError, ValueError):
            raise ValidationError("El número inicial debe ser un valor numérico")
        
        try:
            if self.proximo_numero is not None:
                self.proximo_numero = int(self.proximo_numero)
        except (TypeError, ValueError):
            raise ValidationError("El próximo número debe ser un valor numérico")
        
        # 1. Validar rango
        if self.numero_final <= self.numero_inicial:
            raise ValidationError(
                f"El número final ({self.numero_final}) debe ser mayor que el inicial ({self.numero_inicial})"
            )
       
        # 2. Validar que proximo_numero esté dentro del rango
        if self.proximo_numero < self.numero_inicial:
            raise ValidationError(
                f"El próximo número ({self.proximo_numero}) no puede ser menor que el inicial ({self.numero_inicial})"
            )
       
        if self.proximo_numero > self.numero_final:
            raise ValidationError(
                f"El próximo número ({self.proximo_numero}) no puede ser mayor que el final ({self.numero_final})"
            )
       
        # 3. Validar que no exista otra configuración con mismo tipo+serie
        if self.pk:  # Si ya existe (está siendo actualizado)
            existentes = Comprobante.objects.filter(
                tipo=self.tipo,
                serie=self.serie
            ).exclude(pk=self.pk)
        else:  # Si es nuevo
            existentes = Comprobante.objects.filter(
                tipo=self.tipo,
                serie=self.serie
            )
       
        if existentes.exists():
            raise ValidationError(
                f"Ya existe una configuración para {self.tipo}-{self.serie}"
            )


    def save(self, *args, **kwargs):
        """
        ⭐⭐ SIMPLIFICADO: Solo valida y guarda
        NO calcula números automáticamente
        """
        # Asegurar que los valores sean integers antes de guardar
        self._convertir_campos_a_int()
        self.clean()  # Validar antes de guardar
        super().save(*args, **kwargs)


    def _convertir_campos_a_int(self):
        """Convierte los campos numéricos a int si es necesario"""
        try:
            if self.proximo_numero is not None:
                self.proximo_numero = int(float(str(self.proximo_numero).strip()))
        except (ValueError, TypeError):
            self.proximo_numero = 1
            
        try:
            if self.numero_final is not None:
                self.numero_final = int(float(str(self.numero_final).strip()))
        except (ValueError, TypeError):
            self.numero_final = 999999
            
        try:
            if self.numero_inicial is not None:
                self.numero_inicial = int(float(str(self.numero_inicial).strip()))
        except (ValueError, TypeError):
            self.numero_inicial = 1


    @transaction.atomic
    def obtener_siguiente_numero(self):
        """
        ⭐⭐ MÉTODO PRINCIPAL: Obtiene el siguiente número disponible
       
        Se llama desde la API cuando Tkinter necesita un número nuevo.
        Incrementa automáticamente proximo_numero para el próximo uso.
       
        Returns:
            int: El número asignado (ej: 255)
       
        Raises:
            ValidationError: Si no hay números disponibles
        """
        try:
            # Bloquear este registro para evitar que otro proceso use el mismo número
            comprobante = Comprobante.objects.select_for_update().get(pk=self.pk)
            
            # DEBUG: Verificar valores antes de procesar
            print(f"🔍 DEBUG obtener_siguiente_numero - ID: {comprobante.id}")
            print(f"  proximo_numero raw: {comprobante.proximo_numero} (type: {type(comprobante.proximo_numero)})")
            print(f"  numero_final raw: {comprobante.numero_final} (type: {type(comprobante.numero_final)})")
            
            # ⭐⭐ CORRECCIÓN CRÍTICA: Usar comprobante._convertir_a_int() NO self._convertir_a_int()
            numero_asignado = comprobante._convertir_a_int(comprobante.proximo_numero, 1)
            numero_final = comprobante._convertir_a_int(comprobante.numero_final, 999999)
            numero_inicial = comprobante._convertir_a_int(comprobante.numero_inicial, 1)
            
            print(f"  numero_asignado conv: {numero_asignado} (type: {type(numero_asignado)})")
            print(f"  numero_final conv: {numero_final} (type: {type(numero_final)})")
            
            # Verificar que haya números disponibles
            if numero_asignado > numero_final:
                raise ValidationError(
                    f"❌ RANGO AGOTADO\n"
                    f"Configuración: {comprobante.tipo}-{comprobante.serie}\n"
                    f"Rango: {numero_inicial} - {numero_final}\n"
                    f"Último usado: {numero_asignado - 1}"
                )
            
            # ⭐⭐ INCREMENTAR para el próximo uso
            nuevo_proximo = numero_asignado + 1
            
            # Actualizar el objeto
            comprobante.proximo_numero = nuevo_proximo
            
            # Asegurar que se guarde como int
            comprobante._convertir_campos_a_int()
            
            # Guardar los cambios
            comprobante.save(update_fields=['proximo_numero'])
            
            print(f"✅ Número asignado: {numero_asignado}")
            print(f"✅ Nuevo proximo_numero: {comprobante.proximo_numero}")
            
            return numero_asignado
            
        except ValidationError:
            # Re-lanzar ValidationError para que se maneje arriba
            raise
        except Exception as e:
            # Cualquier otro error
            raise ValidationError(f"Error inesperado al obtener número: {str(e)}")


    @property
    def numeros_disponibles(self):
        """Cuántos números quedan disponibles en el rango - VERSIÓN SEGURA"""
        try:
            # Convertir siempre a int
            proximo = self._convertir_a_int(self.proximo_numero, 1)
            final = self._convertir_a_int(self.numero_final, 999999)
            disponibles = final - proximo + 1
            return max(disponibles, 0)
        except Exception:
            return 0


    @property
    def numeros_usados(self):
        """Cuántos números se han usado (incluyendo el próximo a usar) - VERSIÓN SEGURA"""
        try:
            proximo = self._convertir_a_int(self.proximo_numero, 1)
            inicial = self._convertir_a_int(self.numero_inicial, 1)
            return proximo - inicial
        except Exception:
            return 0


    @property
    def porcentaje_usado(self):
        """Porcentaje del rango que se ha usado - VERSIÓN SEGURA"""
        try:
            usados = self.numeros_usados
            inicial = self._convertir_a_int(self.numero_inicial, 1)
            final = self._convertir_a_int(self.numero_final, 999999)
            total = final - inicial + 1
            if total <= 0:
                return 0
            return round((usados / total) * 100, 1)
        except Exception:
            return 0


    @property
    def esta_agotado(self):
        """Verificar si el rango está agotado - VERSIÓN CORREGIDA"""
        try:
            # Convertir siempre a int, sin importar el tipo original
            proximo = self._convertir_a_int(self.proximo_numero, 1)
            final = self._convertir_a_int(self.numero_final, 999999)
            return proximo > final
        except Exception:
            return False


    def _convertir_a_int(self, valor, valor_por_defecto=0):
        """Método helper para convertir cualquier valor a int de forma segura"""
        if valor is None:
            return valor_por_defecto
            
        try:
            # Si ya es int, retornarlo
            if isinstance(valor, int):
                return valor
                
            # Si es float, convertirlo
            if isinstance(valor, float):
                return int(valor)
                
            # Si es string, intentar convertir
            if isinstance(valor, str):
                # Remover espacios y caracteres no numéricos
                valor_limpio = valor.strip()
                if not valor_limpio:
                    return valor_por_defecto
                
                # Intentar convertir a float primero (por si hay decimales)
                return int(float(valor_limpio))
                
            # Para cualquier otro tipo, intentar conversión
            return int(valor)
        except (ValueError, TypeError, AttributeError):
            return valor_por_defecto


    @property
    def advertencia_rango(self):
        """Mensaje de advertencia si quedan pocos números"""
        disponibles = self.numeros_disponibles
       
        if self.esta_agotado:
            return "❌ RANGO AGOTADO"
        elif disponibles <= 10:
            return f"⚠️ Quedan solo {disponibles} números"
        elif disponibles <= 50:
            return f"ℹ️ Quedan {disponibles} números"
        else:
            return f"✅ {disponibles} números disponibles"


    def __str__(self):
        """Representación legible - VERSIÓN ROBUSTA"""
        try:
            # Obtener valores de forma segura
            try:
                tipo_display = self.get_tipo_display()
            except:
                tipo_display = "Comprobante"
            
            # Obtener serie de forma segura
            serie = self.serie if hasattr(self, 'serie') and self.serie else "00000"
            
            # Obtener números de forma segura usando el método helper
            proximo = self._convertir_a_int(self.proximo_numero, 1)
            inicial = self._convertir_a_int(self.numero_inicial, 1)
            final = self._convertir_a_int(self.numero_final, 999999)
            
            # Determinar estado de forma segura
            try:
                if proximo > final:
                    estado = "AGOTADO"
                elif self.numeros_disponibles <= 10:
                    estado = "POCO STOCK"
                else:
                    estado = "OK"
            except:
                estado = "OK"
            
            return (
                f"{tipo_display} {serie} | "
                f"Próximo: {proximo:06d} | "
                f"Rango: {inicial}-{final} | "
                f"Estado: {estado}"
            )
            
        except Exception as e:
            # Fallback absoluto
            try:
                return f"Configuración ID: {self.id}"
            except:
                return "Configuración de Numeración"


    @classmethod
    def get_or_create_config(cls, tipo="PRES", serie="00001"):
        """
        Método de conveniencia: Obtiene o crea una configuración
       
        Args:
            tipo (str): Tipo de comprobante (PRES/REMI)
            serie (str): Serie (00001, 00002, etc.)
       
        Returns:
            Comprobante: Configuración existente o nueva
        """
        config, created = cls.objects.get_or_create(
            tipo=tipo,
            serie=serie,
            defaults={
                'numero_inicial': 1,
                'numero_final': 999999,
                'proximo_numero': 1
            }
        )
       
        if created:
            print(f"✅ Configuración creada: {tipo}-{serie}")
        else:
            print(f"✅ Configuración encontrada: {tipo}-{serie}")
           
        return config


    @classmethod
    def verificar_y_corregir_registros(cls):
        """
        Verifica y corrige registros con valores incorrectos
        Útil para ejecutar después de migraciones o importaciones
        """
        print("\n=== VERIFICACIÓN Y CORRECCIÓN DE REGISTROS ===")
        registros_corregidos = 0
        
        for comp in cls.objects.all():
            necesita_correccion = False
            
            # Verificar cada campo
            campos_a_verificar = [
                ('proximo_numero', 1),
                ('numero_inicial', 1),
                ('numero_final', 999999)
            ]
            
            for campo, valor_por_defecto in campos_a_verificar:
                valor = getattr(comp, campo)
                if valor is not None and not isinstance(valor, int):
                    print(f"⚠️  ID {comp.id}: Campo '{campo}' no es int: {valor} (type: {type(valor)})")
                    necesita_correccion = True
            
            if necesita_correccion:
                try:
                    # Guardar el objeto para que se aplique la conversión automática
                    comp.save()
                    registros_corregidos += 1
                    print(f"✅ ID {comp.id}: Registro corregido")
                except Exception as e:
                    print(f"❌ ID {comp.id}: Error corrigiendo: {e}")
        
        print(f"\n=== RESUMEN: {registros_corregidos} registros corregidos ===")
        return registros_corregidos


    @classmethod
    def corregir_valores_incorrectos(cls):
        """
        Corrección específica para el error donde los campos tienen strings incorrectos
        """
        print("\n=== CORRECCIÓN DE VALORES INCORRECTOS ===")
        registros_corregidos = 0
        
        for comp in cls.objects.all():
            cambios = []
            
            # Lista de campos y sus valores por defecto
            campos = [
                ('proximo_numero', 1),
                ('numero_inicial', 1),
                ('numero_final', 999999)
            ]
            
            for campo_nombre, valor_default in campos:
                valor_actual = getattr(comp, campo_nombre)
                valor_original = valor_actual
                
                # Si es None, establecer valor por defecto
                if valor_actual is None:
                    setattr(comp, campo_nombre, valor_default)
                    cambios.append(f"{campo_nombre}: None → {valor_default}")
                
                # Si es string, verificar
                elif isinstance(valor_actual, str):
                    valor_limpio = valor_actual.strip()
                    
                    # Si es el nombre del campo o no es numérico
                    if (valor_limpio.lower() == campo_nombre.lower() or 
                        valor_limpio.lower() == 'proximo_numero' or
                        not valor_limpio.replace('.', '', 1).replace('-', '', 1).isdigit()):
                        
                        # Usar valor por defecto o el del otro campo si corresponde
                        if campo_nombre == 'proximo_numero':
                            nuevo_valor = comp.numero_inicial if comp.numero_inicial else valor_default
                        else:
                            nuevo_valor = valor_default
                        
                        setattr(comp, campo_nombre, nuevo_valor)
                        cambios.append(f"{campo_nombre}: '{valor_original}' → {nuevo_valor}")
            
            # Si hubo cambios, guardar
            if cambios:
                try:
                    comp._convertir_campos_a_int()
                    comp.save()
                    registros_corregidos += 1
                    print(f"\n✅ ID {comp.id}: Registro corregido")
                    for cambio in cambios:
                        print(f"   {cambio}")
                except Exception as e:
                    print(f"\n❌ ID {comp.id}: Error guardando cambios: {e}")
        
        print(f"\n=== RESUMEN: {registros_corregidos} registros corregidos ===")
        return registros_corregidos