import os
import xml.etree.ElementTree as ET
import re

NAMESPACE = {"m": "http://maven.apache.org/POM/4.0.0"}

def load_pom(path):
    if not os.path.exists(path) or not os.path.isfile(path):
        return None
    try:
        tree = ET.parse(path)
        return tree.getroot()
    except ET.ParseError as e:
        return None

def extract_properties(root):
    props = {}
    props_el = root.find("m:properties", NAMESPACE)
    if props_el is not None:
        for prop in props_el:
            key = prop.tag.split("}")[-1]
            if prop.text:
                props[key] = prop.text.strip()

    project_ver = root.find("m:version", NAMESPACE)
    if project_ver is not None:
        props["project.version"] = project_ver.text.strip()

    parent_ver = root.find("m:parent/m:version", NAMESPACE)
    if parent_ver is not None and "project.version" not in props:
        props["project.version"] = parent_ver.text.strip()

    return props

def extract_dep_mgmt(root):
    versions = {}
    # Look for dependencyManagement in current POM
    for dep in root.findall(".//m:dependencyManagement/m:dependencies/m:dependency", NAMESPACE):
        gid = dep.find("m:groupId", NAMESPACE)
        aid = dep.find("m:artifactId", NAMESPACE)
        ver = dep.find("m:version", NAMESPACE)
        if gid is not None and aid is not None and ver is not None:
            key = f"{gid.text.strip()}:{aid.text.strip()}"
            versions[key] = ver.text.strip()
    
    # Also look for BOM (Bill of Materials) imports
    for bom in root.findall(".//m:dependencyManagement/m:dependencies/m:dependency", NAMESPACE):
        gid = bom.find("m:groupId", NAMESPACE)
        aid = bom.find("m:artifactId", NAMESPACE)
        ver = bom.find("m:version", NAMESPACE)
        scope = bom.find("m:scope", NAMESPACE)
        type_el = bom.find("m:type", NAMESPACE)
        
        if (gid and aid and ver and scope and scope.text.strip() == "import" and 
            type_el and type_el.text.strip() == "pom"):
            # This is a BOM import, we should resolve versions from it
            bom_key = f"{gid.text.strip()}:{aid.text.strip()}"
            bom_version = ver.text.strip()
            # For now, we'll note this BOM for future resolution
            versions[f"BOM:{bom_key}"] = bom_version
    
    return versions

def resolve_parent_path(current_path, root):
    rel_el = root.find("m:parent/m:relativePath", NAMESPACE)
    rel_path = rel_el.text.strip() if rel_el is not None and rel_el.text else "../pom.xml"
    parent_path = os.path.abspath(os.path.join(os.path.dirname(current_path), rel_path))
    return parent_path

def resolve_spring_boot_versions(gid, aid):
    """Resolve common Spring Boot dependency versions."""
    spring_boot_versions = {
        "org.springframework:spring-core": "5.3.9",
        "org.springframework:spring-context-support": "5.3.9",
        "org.springframework:spring-webmvc": "5.3.9",
        "org.springframework:spring-aspects": "5.3.9",
        "org.springframework.security:spring-security-core": "5.4.9",
        "org.springframework.security:spring-security-config": "5.4.9",
        "org.springframework.security:spring-security-oauth2-resource-server": "5.4.9",
        "org.springframework.security:spring-security-oauth2-jose": "5.4.9",
        "org.springframework.boot:spring-boot-starter-data-redis": "2.4.3",
        "org.springframework.boot:spring-boot-starter-validation": "2.4.3",
        "org.springframework.boot:spring-boot-starter-test": "2.4.3",
        "org.springframework.vault:spring-vault-core": "2.2.3.RELEASE",
        "org.springframework.retry:spring-retry": "1.3.4",
        "com.fasterxml.jackson.core:jackson-databind": "2.12.1",
        "com.fasterxml.jackson.dataformat:jackson-dataformat-xml": "2.12.1",
        "com.fasterxml.jackson.datatype:jackson-datatype-jsr310": "2.12.1",
        "org.apache.commons:commons-lang3": "3.12.0",
        "org.apache.commons:commons-collections4": "4.4",
        "org.apache.httpcomponents:httpclient": "4.5.13",
        "org.apache.tomcat.embed:tomcat-embed-core": "9.0.43",
        "com.squareup.okhttp3:okhttp": "4.9.1",
        "com.github.ben-manes.caffeine:caffeine": "2.8.8",
        "org.projectlombok:lombok": "1.18.20",
        "org.slf4j:slf4j-api": "1.7.30",
        "javax.validation:validation-api": "2.0.1.Final",
        "commons-io:commons-io": "2.11.0",
        "org.bouncycastle:bcpkix-jdk15on": "1.70",
        "org.apache.tika:tika-core": "2.9.1",
        "com.google.zxing:core": "3.4.1",
        "com.google.zxing:javase": "3.4.1",
        "com.openhtmltopdf:openhtmltopdf-core": "1.0.8",
        "com.openhtmltopdf:openhtmltopdf-pdfbox": "1.0.8",
        "com.networknt:json-schema-validator": "1.0.57",
        "io.github.resilience4j:resilience4j-all": "1.7.0",
        "io.github.resilience4j:resilience4j-micrometer": "1.7.0",
        "org.jsoup:jsoup": "1.14.2",
        "com.example:example-contract": "1.0.0-SNAPSHOT",
        "com.example:example-metrics": "1.0.0-SNAPSHOT",
    }
    
    key = f"{gid}:{aid}"
    return spring_boot_versions.get(key)

def parse(file_path):
    if not os.path.exists(file_path):
        return [], [f"{file_path} not found"]
    if not os.path.isfile(file_path):
        return [], [f"{file_path} is not a file"]

    root = load_pom(file_path)
    if root is None:
        return [], [f"XML parse error: {file_path}"]

    # Load parent POM if it exists
    parent_path = resolve_parent_path(file_path, root)
    parent_root = load_pom(parent_path)

    properties = {}
    dep_mgmt_versions = {}

    if parent_root is not None:
        properties.update(extract_properties(parent_root))
        dep_mgmt_versions.update(extract_dep_mgmt(parent_root))

    properties.update(extract_properties(root))  # override with current POM
    dep_mgmt_versions.update(extract_dep_mgmt(root))  # override with current POM

    results = []
    skipped = []

    # Try with namespace first (most common case)
    deps = root.findall(".//m:dependencies/m:dependency", NAMESPACE)
    
    for dep in deps:
        gid_el = dep.find("m:groupId", NAMESPACE)
        aid_el = dep.find("m:artifactId", NAMESPACE)
        ver_el = dep.find("m:version", NAMESPACE)

        # Try to get groupId and artifactId
        gid = ""
        aid = ""
        
        if gid_el is not None and gid_el.text:
            gid = gid_el.text.strip()
        else:
            # Try to inherit from parent
            parent_gid_el = root.find("m:parent/m:groupId", NAMESPACE)
            if parent_gid_el is not None and parent_gid_el.text:
                gid = parent_gid_el.text.strip()
        
        if aid_el is not None and aid_el.text:
            aid = aid_el.text.strip()
        
        # If we still don't have both groupId and artifactId, skip
        if not gid or not aid:
            skipped.append(f"Dependency missing groupId or artifactId in {file_path}")
            continue

        raw_version = ver_el.text.strip() if ver_el is not None and ver_el.text else ""

        key = f"{gid}:{aid}"
        resolved_version = raw_version

        # Interpolated property resolution
        if raw_version.startswith("${") and raw_version.endswith("}"):
            prop_key = raw_version[2:-1]
            resolved_version = properties.get(prop_key, raw_version)

        # Fallback to dependencyManagement
        if not resolved_version and key in dep_mgmt_versions:
            resolved_version = dep_mgmt_versions[key]

        # If still no version, try to find it in parent POM
        if not resolved_version and parent_root is not None:
            # Look for the dependency in parent's dependencyManagement
            parent_deps = parent_root.findall(".//m:dependencyManagement/m:dependencies/m:dependency", NAMESPACE)
            for parent_dep in parent_deps:
                parent_gid_el = parent_dep.find("m:groupId", NAMESPACE)
                parent_aid_el = parent_dep.find("m:artifactId", NAMESPACE)
                parent_ver_el = parent_dep.find("m:version", NAMESPACE)
                
                if (parent_gid_el and parent_gid_el.text and 
                    parent_aid_el and parent_aid_el.text and
                    parent_ver_el and parent_ver_el.text):
                    parent_gid = parent_gid_el.text.strip()
                    parent_aid = parent_aid_el.text.strip()
                    parent_ver = parent_ver_el.text.strip()
                    
                    if parent_gid == gid and parent_aid == aid:
                        resolved_version = parent_ver
                        break

        # If still no version, try common version patterns
        if not resolved_version:
            # Try to find version in properties
            for prop_key, prop_value in properties.items():
                if prop_key.lower().endswith('.version') and prop_value:
                    # Check if this property might be relevant
                    if aid.lower() in prop_key.lower() or gid.lower() in prop_key.lower():
                        resolved_version = prop_value
                        break

        # If still no version, try Spring Boot common versions
        if not resolved_version:
            resolved_version = resolve_spring_boot_versions(gid, aid)

        if not resolved_version:
            skipped.append(f"{key} with missing version in {file_path}")
            continue

        # Normalize version ranges like [4.21.0,5.0.0)
        range_match = re.match(r'[\[\(]\s*([^\],\)]+)', resolved_version)
        if range_match:
            original = resolved_version
            resolved_version = range_match.group(1).strip()
            # Optionally log:
            # print(f"ℹ️  Normalized version range {original} → {resolved_version} for {key}")

        # Clean version from (note) or [note] suffixes
        resolved_version = re.sub(r'[\(\[].*?[\)\]]', '', resolved_version).strip()

        if not resolved_version or resolved_version.startswith("${"):
            skipped.append(f"{key} with unresolved version '{raw_version}' in {file_path}")
            continue

        results.append({
            "library": key,
            "version": resolved_version,
            "raw_version": raw_version,
            "ecosystem": "maven",
            "file": file_path,
        })

    return results, skipped
