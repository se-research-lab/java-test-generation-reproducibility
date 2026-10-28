/*
 * Copyright 2018 Nokia Solutions and Networks
 * Licensed under the Apache License, Version 2.0,
 * see license.txt file for details.
 */
package org.robotframework.ide.eclipse.main.plugin.project.build.fix;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.eclipse.core.resources.IMarker;
import org.eclipse.jface.text.IDocument;
import org.eclipse.jface.text.IRegion;
import org.eclipse.jface.text.Region;
import org.eclipse.jface.text.contentassist.ICompletionProposal;
import org.rf.ide.core.testdata.model.AModelElement;
import org.rf.ide.core.testdata.model.ModelType;
import org.rf.ide.core.testdata.model.TemplateSetting;
import org.rf.ide.core.testdata.model.table.LocalSetting;
import org.rf.ide.core.testdata.text.read.recognizer.RobotToken;
import org.robotframework.ide.eclipse.main.plugin.RedImages;
import org.robotframework.ide.eclipse.main.plugin.model.RobotElement;
import org.robotframework.ide.eclipse.main.plugin.model.RobotFileInternalElement;
import org.robotframework.ide.eclipse.main.plugin.model.RobotSuiteFile;
import org.robotframework.ide.eclipse.main.plugin.project.build.RobotProblem;
import org.robotframework.ide.eclipse.main.plugin.tableeditor.source.assist.RedCompletionBuilder;
import org.robotframework.red.graphics.ImagesManager;

import com.google.common.collect.Range;

public class JoinTemplateNameFixer extends RedSuiteMarkerResolution {

    // Joins Test Template keyword written in multiple cells:
    // *** Settings ***
    // Test Template    key    word
    //
    // ->
    // *** Settings ***
    // Test Template    key word

    @Override
    public String getLabel() {
        return "Merge name into single cell";
    }

    @Override
    public Optional<ICompletionProposal> asContentProposal(final IMarker marker, final IDocument document,
            final RobotSuiteFile suiteModel) {
        
        final Range<Integer> range = RobotProblem.getRangeOf(marker);
        final Optional<? extends RobotElement> element = suiteModel.findElement(range.lowerEndpoint());
        return element.filter(RobotFileInternalElement.class::isInstance)
                .map(RobotFileInternalElement.class::cast)
                .map(RobotFileInternalElement::getLinkedElement)
                .filter(AModelElement.class::isInstance)
                .map(AModelElement.class::cast)
                .filter(elem -> elem.getModelType() == ModelType.TEST_CASE_TEMPLATE
                        || elem.getModelType() == ModelType.TASK_TEMPLATE
                        || elem.getModelType() == ModelType.SUITE_TEST_TEMPLATE
                        || elem.getModelType() == ModelType.SUITE_TASK_TEMPLATE)
                .map(elem -> createProposal(document, suiteModel, elem));
    }

    private ICompletionProposal createProposal(final IDocument document, final RobotSuiteFile suiteModel,
            final AModelElement<?> templateSetting) {

        TemplateSetting template;
        if (templateSetting instanceof TemplateSetting) {
            template = (TemplateSetting) templateSetting;
        } else if (templateSetting instanceof LocalSetting<?>) {
            template = ((LocalSetting<?>) templateSetting).adaptTo(TemplateSetting.class);
        } else {
            throw new IllegalStateException();
        }

        final RobotToken declaration = template.getDeclaration();
        final int offset = declaration.getStartOffset();

        final List<RobotToken> elements = template.getUnexpectedArguments();
        final IRegion toChange = new Region(offset, elements.get(elements.size() - 1).getEndOffset() - offset);
        final String cellSeparator = getSeparator(suiteModel, offset);

        final List<String> nameParts = new ArrayList<>();
        nameParts.add(template.getKeywordName().getText());
        template.getUnexpectedArguments().stream().map(RobotToken::getText).forEach(nameParts::add);
        final String joinedName = String.join(" ", nameParts);

        final String correctedTemplate = declaration.getText() + cellSeparator + joinedName;

        final String info = Snippets.createSnippetInfo(document, toChange, correctedTemplate);
        return RedCompletionBuilder.newProposal()
                .willPut(correctedTemplate)
                .byReplacingRegion(toChange)
                .secondaryPopupShouldBeDisplayedUsingHtml(info)
                .thenCursorWillStopAtTheEndOfInsertion()
                .displayedLabelShouldBe(getLabel())
                .proposalsShouldHaveIcon(ImagesManager.getImage(RedImages.getRobotSettingImage()))
                .create();
    }
}
